"""MDX validate + migration-diff evidence (ADR 0008 validate stage, #172)."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any

from stars._core.migration_profile import MigrationProfileError, require_profile
from stars._core.migration_run import MigrationRunStore, build_change_bundle
from stars._core.migration_validate import run_validate_stage, validate_change_bundle
from stars.docs_myst_inventory.service import inventory as build_source_inventory

from .contract import (
    MAX_ENTRIES,
    MAX_ENTRY_BYTES,
    MAX_FINDINGS,
    MAX_MESSAGE_BYTES,
    MAX_PATH_LEN,
    VALIDATOR_NAME,
)
from .diff import build_migration_diff, semantic_loss_findings
from .mdx_check import check_mdx_buildable
from .target_inventory import inventory_targets


def validate(
    source_entries: Sequence[Mapping[str, Any]] | None = None,
    target_entries: Sequence[Mapping[str, Any]] | None = None,
    change_bundle: Mapping[str, Any] | None = None,
    profile: Mapping[str, Any] | None = None,
    plan: Mapping[str, Any] | None = None,
    link_asset_report: Mapping[str, Any] | None = None,
    *,
    store: MigrationRunStore | None = None,
) -> dict[str, object]:
    """Validate MDX targets against a sealed change_bundle and emit migration-diff."""
    sources, source_error = _normalize_entries(source_entries, field="source_entries")
    if source_error is not None:
        return source_error
    targets, target_error = _normalize_entries(target_entries, field="target_entries")
    if target_error is not None:
        return target_error
    pinned, profile_error = _pin_profile(profile)
    if profile_error is not None:
        return profile_error
    assert sources is not None and targets is not None and pinned is not None

    if pinned["validator"].get("name") != VALIDATOR_NAME:
        return {
            "error": "validator_name_mismatch",
            "expected": VALIDATOR_NAME,
            "received": pinned["validator"].get("name"),
        }

    bundle, bundle_error = _require_bundle(change_bundle)
    if bundle_error is not None:
        return bundle_error
    assert bundle is not None

    if plan is not None:
        if not isinstance(plan, Mapping):
            return {"error": "plan_invalid"}
        plan_digest = plan.get("plan_digest")
        if not isinstance(plan_digest, str) or not plan_digest:
            return {"error": "plan_digest_required"}
        if plan_digest != bundle["plan_digest"]:
            return {
                "error": "plan_digest_mismatch",
                "expected": plan_digest,
                "received": bundle["plan_digest"],
            }

    source_analysis = build_source_inventory(sources)
    if "error" in source_analysis:
        return dict(source_analysis)

    build_status = check_mdx_buildable(targets)
    target_inv = inventory_targets(targets)

    # Serialize raw findings from target inventory for digesting only.
    target_constructs = list(target_inv["constructs"])

    diff = build_migration_diff(
        source_findings=list(source_analysis["findings"]),
        target_constructs=target_constructs,
        file_entries=list(bundle["file_entries"]),
        source_paths={entry["path"] for entry in sources},
        target_paths={entry["path"] for entry in targets},
        link_asset_report=link_asset_report,
        build_status=build_status,
    )

    findings: list[dict[str, object]] = []
    findings.extend(dict(item) for item in build_status["findings"])
    findings.extend(semantic_loss_findings(diff))
    findings.sort(
        key=lambda item: (
            str(item.get("path", "")),
            str(item.get("feature_id", "")),
            str(item.get("class", "")),
            str(item.get("message", "")),
        )
    )
    findings_truncated = len(findings) > MAX_FINDINGS
    if findings_truncated:
        findings = findings[:MAX_FINDINGS]

    diagnostics = {
        "build_passed": bool(build_status["passed"]),
        "semantic_loss_count": len(diff["dropped_constructs"])
        + len(diff["added_constructs"]),
        "unresolved_link_count": len(diff["unresolved_links"]),
        "unresolved_asset_count": len(diff["unresolved_assets"]),
        "mapping_complete": bool(diff["mapping_coverage"]["complete"]),
        "source_entry_count": len(sources),
        "target_entry_count": len(targets),
        "findings_truncated": findings_truncated,
        # Never include raw source/target bytes in diagnostics.
    }

    report_body = {
        "source_manifest_digest": source_analysis["source_manifest_digest"],
        "source_inventory_digest": source_analysis["inventory_digest"],
        "target_constructs": target_constructs,
        "migration_diff": diff,
        "bundle_digest": bundle["bundle_digest"],
        "profile_digest": pinned["profile_digest"],
    }
    report_digest = _digest(report_body)

    checker_passed = bool(build_status["passed"])
    adapter = validate_change_bundle(
        pinned,
        bundle,
        findings=findings,
        diagnostics=diagnostics,
        checker_passed=checker_passed,
    )
    if "error" in adapter:
        return dict(adapter)

    result: dict[str, object] = {
        "validation": adapter["validation"],
        "validation_passed": adapter["validation_passed"],
        "validation_digest": adapter["validation"]["validation_digest"],
        "diagnostics": adapter["diagnostics"],
        "diagnostics_digest": adapter["validation"]["diagnostics_digest"],
        "migration_diff": diff,
        "report_digest": report_digest,
        "source_manifest_digest": source_analysis["source_manifest_digest"],
        "source_inventory_digest": source_analysis["inventory_digest"],
        "bundle_digest": bundle["bundle_digest"],
        "profile_digest": pinned["profile_digest"],
        "profile_id": adapter["profile_id"],
        "profile_version": adapter["profile_version"],
        "target": adapter["target"],
        "validator": adapter["validator"],
        "build_status": build_status,
        "finding_count": len(findings),
        "findings": findings,
        "findings_truncated": findings_truncated,
        "entry_count": len(sources),
    }

    if store is not None:
        sealed = run_validate_stage(
            store,
            profile=pinned,
            source_manifest_digest=str(source_analysis["source_manifest_digest"]),
            bundle=bundle,
            findings=findings,
            diagnostics=diagnostics,
            checker_passed=checker_passed,
        )
        if "error" in sealed:
            return dict(sealed)
        result["sealed_stage"] = sealed
        # Failures must seal with passed=false — already enforced by adapter.
        assert sealed["validation_passed"] is adapter["validation_passed"]

    return result


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        _nfc_normalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _require_bundle(
    bundle: Mapping[str, Any] | None,
) -> tuple[dict[str, Any] | None, dict[str, object] | None]:
    if bundle is None:
        return None, {"error": "change_bundle_required"}
    if not isinstance(bundle, Mapping):
        return None, {"error": "change_bundle_invalid"}
    required = (
        "plan_digest",
        "patch_digest",
        "file_entries",
        "mapping_digest",
        "warnings",
        "bundle_digest",
    )
    missing = [key for key in required if key not in bundle]
    if missing:
        return None, {"error": "change_bundle_missing_fields", "missing": missing}
    if not isinstance(bundle["file_entries"], list):
        return None, {"error": "file_entries_invalid"}

    recomputed = build_change_bundle(
        plan_digest=str(bundle["plan_digest"]),
        patch_digest=str(bundle["patch_digest"]),
        file_entries=list(bundle["file_entries"]),
        mapping_digest=str(bundle["mapping_digest"]),
        warnings=list(bundle.get("warnings") or []),
    )
    if recomputed["bundle_digest"] != bundle["bundle_digest"]:
        return None, {
            "error": "bundle_digest_mismatch",
            "expected": recomputed["bundle_digest"],
            "received": bundle["bundle_digest"],
        }
    return dict(bundle), None


def _normalize_entries(
    entries: Sequence[Mapping[str, Any]] | None,
    *,
    field: str,
) -> tuple[list[dict[str, str]] | None, dict[str, object] | None]:
    if entries is None:
        return None, {"error": f"{field}_required"}
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        return None, {"error": f"{field}_invalid"}

    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in entries:
        if not isinstance(item, Mapping):
            return None, {"error": "entry_invalid", "field": field}
        path = item.get("path")
        content = item.get("content")
        if not isinstance(path, str) or not path.strip():
            return None, {"error": "path_invalid", "path": path, "field": field}
        if len(path) > MAX_PATH_LEN:
            return None, {"error": "path_too_long", "path": path, "field": field}
        if not isinstance(content, str):
            return None, {"error": "content_invalid", "path": path, "field": field}
        if path in seen:
            return None, {"error": "path_duplicate", "path": path, "field": field}
        content_bytes = unicodedata.normalize("NFC", content).encode("utf-8")
        if len(content_bytes) > MAX_ENTRY_BYTES:
            return None, {"error": "content_too_large", "path": path, "field": field}
        if len(path.encode("utf-8")) > MAX_MESSAGE_BYTES:
            return None, {"error": "path_too_long", "path": path, "field": field}
        seen.add(path)
        normalized.append({"path": path, "content": content})

    if not normalized:
        return None, {"error": f"{field}_empty"}
    if len(normalized) > MAX_ENTRIES:
        return None, {"error": f"{field}_too_many", "count": len(normalized)}
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
    return dict(pinned), None


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
