"""Safe OpenAPI 3.0→3.1 plan/apply per ADR 0008 stage artifacts (#175)."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any

from stars._core.migration_profile import MigrationProfileError, require_profile
from stars._core.migration_run import build_change_bundle, build_plan
from stars.api_spec_openapi_inventory.service import inventory as build_inventory

from .contract import (
    CORPUS_FEATURES,
    CORPUS_SAFE_FEATURES,
    CORPUS_TRANSFORMABLE_FEATURES,
    HOLD_CLASSES,
    MAX_ENTRIES,
    MAX_ENTRY_BYTES,
    MAX_FINDINGS,
    MAX_MESSAGE_BYTES,
    PINNED_PROFILE_ID,
    PINNED_SOURCE,
    PINNED_TARGET,
)
from .transform import target_openapi_parseable, transform_document


def plan(
    entries: Sequence[Mapping[str, Any]] | None = None,
    profile: Mapping[str, Any] | None = None,
) -> dict[str, object]:
    """Build an ADR 0008 plan for the corpus-backed OpenAPI 3.0→3.1 subset."""
    normalized, error = _normalize_entries(entries)
    if error is not None:
        return error
    pinned, profile_error = _pin_profile(profile)
    if profile_error is not None:
        return profile_error
    assert normalized is not None and pinned is not None

    analysis = build_inventory(normalized)
    if "error" in analysis:
        return dict(analysis)

    findings = list(analysis["findings"])
    planned_ops = _planned_ops(findings, pinned)
    plan_body = build_plan(
        analysis_digest=str(analysis["analysis_digest"]),
        profile_digest=str(pinned["profile_digest"]),
        policy_id=str(pinned["compatibility_policy"]["policy_id"]),
        planned_ops=planned_ops,
    )
    return {
        **plan_body,
        "source_manifest_digest": analysis["source_manifest_digest"],
        "findings": findings,
        "findings_truncated": analysis.get("findings_truncated", False),
        "entry_count": analysis["entry_count"],
        "finding_count": analysis["finding_count"],
        "analysis_digest": analysis["analysis_digest"],
        "source": analysis.get("source"),
        "target": dict(pinned["target"]),
    }


def apply(
    entries: Sequence[Mapping[str, Any]] | None = None,
    plan_payload: Mapping[str, Any] | None = None,
    profile: Mapping[str, Any] | None = None,
) -> dict[str, object]:
    """Apply a sealed plan; return change_bundle + targets (no checkout writes)."""
    normalized, error = _normalize_entries(entries)
    if error is not None:
        return error
    pinned, profile_error = _pin_profile(profile)
    if profile_error is not None:
        return profile_error
    if not isinstance(plan_payload, Mapping):
        return {"error": "plan_required"}
    assert normalized is not None and pinned is not None

    required = ("plan_digest", "analysis_digest", "profile_digest", "planned_ops")
    missing = [key for key in required if key not in plan_payload]
    if missing:
        return {"error": "plan_missing_fields", "missing": missing}

    if plan_payload["profile_digest"] != pinned["profile_digest"]:
        return {
            "error": "profile_digest_mismatch",
            "expected": pinned["profile_digest"],
            "received": plan_payload["profile_digest"],
        }

    analysis = build_inventory(normalized)
    if "error" in analysis:
        return dict(analysis)

    if plan_payload["analysis_digest"] != analysis["analysis_digest"]:
        return {
            "error": "source_digest_mismatch",
            "expected": analysis["analysis_digest"],
            "received": plan_payload["analysis_digest"],
        }

    source_manifest = str(analysis["source_manifest_digest"])
    plan_source = plan_payload.get("source_manifest_digest")
    if isinstance(plan_source, str) and plan_source != source_manifest:
        return {
            "error": "source_manifest_mismatch",
            "expected": source_manifest,
            "received": plan_source,
        }

    expected_plan = build_plan(
        analysis_digest=str(plan_payload["analysis_digest"]),
        profile_digest=str(plan_payload["profile_digest"]),
        policy_id=_policy_id(plan_payload, pinned),
        planned_ops=list(plan_payload["planned_ops"]),
    )
    if expected_plan["plan_digest"] != plan_payload["plan_digest"]:
        return {
            "error": "plan_digest_mismatch",
            "expected": expected_plan["plan_digest"],
            "received": plan_payload["plan_digest"],
        }

    findings = list(analysis["findings"])
    bump_paths = {
        str(op["path"])
        for op in plan_payload["planned_ops"]
        if isinstance(op, Mapping)
        and op.get("op") in {"bump_openapi", "transform_nullable"}
        and isinstance(op.get("path"), str)
    }
    hold_paths = {
        str(item["path"])
        for item in findings
        if item.get("class") in HOLD_CLASSES and isinstance(item.get("path"), str)
    }
    target_version = str(pinned["target"]["version"])

    targets: list[dict[str, str]] = []
    file_entries: list[dict[str, str]] = []
    mapping_rows: list[dict[str, str]] = []
    patch_rows: list[dict[str, object]] = []

    for entry in normalized:
        path = entry["path"]
        source = unicodedata.normalize("NFC", entry["content"])
        source_digest = _content_digest(source)

        if path in hold_paths:
            # Never silently "upgrade" unsupported / decision-required / malformed.
            target = source
        elif path in bump_paths:
            target = transform_document(
                source,
                target_version=target_version,
                allow_draft_bump=True,
            )
        else:
            target = source

        target = unicodedata.normalize("NFC", target)
        target_digest = _content_digest(target)
        targets.append({"path": path, "content": target})
        file_entries.append(
            {
                "path": path,
                "source_digest": source_digest,
                "target_digest": target_digest,
            }
        )
        mapping_rows.append(
            {
                "source_path": path,
                "target_path": path,
                "source_digest": source_digest,
                "target_digest": target_digest,
            }
        )
        if source_digest != target_digest:
            patch_rows.append(
                {
                    "path": path,
                    "before_sha256": source_digest,
                    "after_sha256": target_digest,
                }
            )

    file_entries.sort(key=lambda item: item["path"])
    mapping_rows.sort(key=lambda item: item["source_path"])
    patch_rows.sort(key=lambda item: str(item["path"]))
    targets.sort(key=lambda item: item["path"])

    mapping_digest = _digest({"mappings": mapping_rows})
    patch_digest = _digest({"changes": patch_rows})

    bundle = build_change_bundle(
        plan_digest=str(plan_payload["plan_digest"]),
        patch_digest=patch_digest,
        file_entries=file_entries,
        mapping_digest=mapping_digest,
        warnings=[],
    )

    safe_targets = [
        item for item in targets if not _path_has_hold_finding(findings, item["path"])
    ]
    validation = target_openapi_parseable(safe_targets)

    return {
        "change_bundle": bundle,
        "bundle_digest": bundle["bundle_digest"],
        "plan_digest": plan_payload["plan_digest"],
        "source_manifest_digest": source_manifest,
        "profile_digest": pinned["profile_digest"],
        "targets": targets,
        "findings": findings,
        "baseline_validation": validation,
        "entry_count": len(normalized),
    }


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        _nfc_normalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _planned_ops(
    findings: Sequence[Mapping[str, Any]],
    pinned: Mapping[str, Any],
) -> list[dict[str, object]]:
    ops: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    source_version = str(pinned["source"]["version"])
    target_version = str(pinned["target"]["version"])

    for item in findings:
        feature_id = str(item.get("feature_id", ""))
        class_ = str(item.get("class", ""))
        path = str(item.get("path", ""))

        if class_ in HOLD_CLASSES:
            key = ("hold", path, feature_id)
            if key not in seen:
                seen.add(key)
                ops.append(
                    {
                        "op": "hold",
                        "path": path,
                        "feature_id": feature_id,
                        "reason": class_,
                    }
                )
            continue

        if feature_id in CORPUS_SAFE_FEATURES:
            key = ("copy_construct", path, feature_id)
            if key not in seen:
                seen.add(key)
                ops.append(
                    {
                        "op": "copy_construct",
                        "path": path,
                        "feature_id": feature_id,
                    }
                )
            continue

        if (
            feature_id == "openapi.json_schema.draft2020"
            and feature_id in CORPUS_TRANSFORMABLE_FEATURES
            and class_ == "transformable"
        ):
            key = ("bump_openapi", path, feature_id)
            if key not in seen:
                seen.add(key)
                ops.append(
                    {
                        "op": "bump_openapi",
                        "path": path,
                        "feature_id": feature_id,
                        "from": source_version,
                        "to": target_version,
                    }
                )
            continue

        if (
            feature_id == "openapi.nullable"
            and feature_id in CORPUS_TRANSFORMABLE_FEATURES
            and class_ == "transformable"
        ):
            key = ("transform_nullable", path, feature_id)
            if key not in seen:
                seen.add(key)
                ops.append(
                    {
                        "op": "transform_nullable",
                        "path": path,
                        "feature_id": feature_id,
                    }
                )
            continue

        # Non-corpus constructs outside this star's named subset — hold.
        if feature_id not in CORPUS_FEATURES and class_ != "safe":
            key = ("hold", path, feature_id)
            if key not in seen:
                seen.add(key)
                ops.append(
                    {
                        "op": "hold",
                        "path": path,
                        "feature_id": feature_id,
                        "reason": "out_of_corpus",
                    }
                )

    ops.sort(
        key=lambda op: (
            str(op.get("path", "")),
            str(op.get("op", "")),
            str(op.get("feature_id", "")),
        )
    )
    if len(ops) > MAX_FINDINGS:
        return ops[:MAX_FINDINGS]
    return ops


def _normalize_entries(
    entries: Sequence[Mapping[str, Any]] | None,
) -> tuple[list[dict[str, str]] | None, dict[str, object] | None]:
    if entries is None:
        return None, {"error": "entries_required"}
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        return None, {"error": "entries_invalid"}

    normalized: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    for item in entries:
        if not isinstance(item, Mapping):
            return None, {"error": "entry_invalid"}
        path = item.get("path")
        content = item.get("content")
        if not isinstance(path, str) or not path.strip():
            return None, {"error": "path_invalid", "path": path}
        if not isinstance(content, str):
            return None, {"error": "content_invalid", "path": path}
        if path in seen_paths:
            return None, {"error": "path_duplicate", "path": path}
        content_bytes = unicodedata.normalize("NFC", content).encode("utf-8")
        if len(content_bytes) > MAX_ENTRY_BYTES:
            return None, {"error": "content_too_large", "path": path}
        if len(path.encode("utf-8")) > MAX_MESSAGE_BYTES:
            return None, {"error": "path_too_long", "path": path}
        seen_paths.add(path)
        normalized.append({"path": path, "content": content})

    if not normalized:
        return None, {"error": "entries_empty"}
    if len(normalized) > MAX_ENTRIES:
        return None, {"error": "entries_too_many", "count": len(normalized)}
    normalized.sort(key=lambda entry: entry["path"])
    return normalized, None


def _pin_profile(
    profile: Mapping[str, Any] | None,
) -> tuple[dict[str, Any] | None, dict[str, object] | None]:
    if profile is None:
        return None, {"error": "profile_required"}
    if not isinstance(profile, Mapping):
        return None, {"error": "profile_invalid"}
    try:
        pinned = require_profile(profile)
    except MigrationProfileError as exc:
        return None, {"error": "profile_invalid", "detail": str(exc)}

    # This star only accepts the pinned 3.0.3→3.1.0 corpus profile — no latest.
    if pinned.get("profile_id") != PINNED_PROFILE_ID:
        return None, {
            "error": "profile_id_unsupported",
            "expected": PINNED_PROFILE_ID,
            "received": pinned.get("profile_id"),
        }
    if pinned.get("source") != PINNED_SOURCE:
        return None, {
            "error": "profile_source_mismatch",
            "expected": dict(PINNED_SOURCE),
            "received": pinned.get("source"),
        }
    if pinned.get("target") != PINNED_TARGET:
        return None, {
            "error": "profile_target_mismatch",
            "expected": dict(PINNED_TARGET),
            "received": pinned.get("target"),
        }
    return dict(pinned), None


def _policy_id(plan_payload: Mapping[str, Any], pinned: Mapping[str, Any]) -> str:
    policy = plan_payload.get("compatibility_policy")
    if isinstance(policy, Mapping) and isinstance(policy.get("policy_id"), str):
        return str(policy["policy_id"])
    return str(pinned["compatibility_policy"]["policy_id"])


def _path_has_hold_finding(findings: Sequence[Mapping[str, Any]], path: str) -> bool:
    return any(
        item.get("path") == path and item.get("class") in HOLD_CLASSES for item in findings
    )


def _nfc_normalize(value: Any) -> Any:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, Mapping):
        return {key: _nfc_normalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_nfc_normalize(item) for item in value]
    return value


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _content_digest(content: str) -> str:
    return hashlib.sha256(unicodedata.normalize("NFC", content).encode("utf-8")).hexdigest()
