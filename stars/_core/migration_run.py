"""Persist migration stages and content-addressed change bundles (ADR 0008)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from .migration_profile import canonical_json, require_profile, sha256_hex

MIGRATION_MODES = frozenset({"analyze", "plan", "apply", "validate"})
STAGE_DIGEST_FIELDS = {
    "analyze": "analysis_digest",
    "plan": "plan_digest",
    "apply": "bundle_digest",
    "validate": "validation_digest",
}

PRIVATE_STATUS_KEYS = frozenset(
    {
        "source_bytes",
        "target_bytes",
        "full_patch_text",
        "private_paths",
        "patch_text",
        "source_content",
        "target_content",
    }
)


class MigrationRunError(ValueError):
    """Migration stage persistence or replay failed."""


class MigrationRunStore:
    """In-memory sealed stage outputs keyed by replay_key and mode."""

    def __init__(self) -> None:
        self._sealed: dict[tuple[str, str], dict[str, Any]] = {}

    def get(self, replay_key: str, mode: str) -> dict[str, Any] | None:
        return self._sealed.get((replay_key, mode))

    def seal(self, replay_key: str, mode: str, output: Mapping[str, Any]) -> dict[str, Any]:
        if mode not in MIGRATION_MODES:
            raise MigrationRunError(f"unknown mode: {mode!r}")
        digest_field = STAGE_DIGEST_FIELDS[mode]
        output_digest = output[digest_field]
        key = (replay_key, mode)
        existing = self._sealed.get(key)
        if existing is not None:
            if existing[digest_field] != output_digest:
                raise MigrationRunError("replay_incompatible")
            return existing
        sealed = dict(output)
        self._sealed[key] = sealed
        return sealed


def compute_replay_key(
    *,
    source_manifest_digest: str,
    profile_digest: str,
    mode: str,
    policy_id: str,
) -> str:
    if mode not in MIGRATION_MODES:
        raise MigrationRunError(f"unknown mode: {mode!r}")
    payload = {
        "source_manifest_digest": source_manifest_digest,
        "profile_digest": profile_digest,
        "mode": mode,
        "policy_id": policy_id,
    }
    return sha256_hex(canonical_json(payload))


def finding_digest(feature_id: str, feature_class: str, path: str, span: str | None = None) -> str:
    body: dict[str, Any] = {
        "feature_id": feature_id,
        "class": feature_class,
        "path": path,
    }
    if span is not None:
        body["span"] = span
    return sha256_hex(canonical_json(body))


def build_analysis(
    *,
    source_manifest_digest: str,
    findings: list[Mapping[str, Any]],
) -> dict[str, Any]:
    bound_findings: list[dict[str, Any]] = []
    for item in findings:
        entry = {
            "feature_id": item["feature_id"],
            "class": item["class"],
            "path": item["path"],
            "finding_digest": item.get("finding_digest")
            or finding_digest(
                str(item["feature_id"]),
                str(item["class"]),
                str(item["path"]),
                item.get("span") if item.get("span") is None else str(item["span"]),
            ),
        }
        if "span" in item and item["span"] is not None:
            entry["span"] = item["span"]
        bound_findings.append(entry)
    body = {
        "source_manifest_digest": source_manifest_digest,
        "findings": bound_findings,
    }
    body["analysis_digest"] = sha256_hex(canonical_json(body))
    return body


def build_plan(
    *,
    analysis_digest: str,
    profile_digest: str,
    policy_id: str,
    planned_ops: list[Mapping[str, Any]],
) -> dict[str, Any]:
    body = {
        "analysis_digest": analysis_digest,
        "profile_digest": profile_digest,
        "compatibility_policy": {"policy_id": policy_id},
        "planned_ops": [dict(item) for item in planned_ops],
    }
    body["plan_digest"] = sha256_hex(canonical_json(body))
    return body


def build_change_bundle(
    *,
    plan_digest: str,
    patch_digest: str,
    file_entries: list[Mapping[str, Any]],
    mapping_digest: str,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    body = {
        "plan_digest": plan_digest,
        "patch_digest": patch_digest,
        "file_entries": [dict(item) for item in file_entries],
        "mapping_digest": mapping_digest,
        "warnings": list(warnings or []),
    }
    body["bundle_digest"] = sha256_hex(canonical_json(body))
    return body


def build_validation(
    *,
    bundle_digest: str,
    validator: Mapping[str, str],
    passed: bool,
    findings: list[Mapping[str, Any]],
    diagnostics_digest: str,
) -> dict[str, Any]:
    body = {
        "bundle_digest": bundle_digest,
        "validator": dict(validator),
        "passed": passed,
        "findings": [dict(item) for item in findings],
        "diagnostics_digest": diagnostics_digest,
    }
    body["validation_digest"] = sha256_hex(canonical_json(body))
    return body


def run_stage(
    store: MigrationRunStore,
    *,
    profile: Mapping[str, Any],
    source_manifest_digest: str,
    mode: str,
    producer: Callable[[], Mapping[str, Any]],
    replay_key: str | None = None,
) -> dict[str, Any]:
    """Run or reuse a migration stage for the given replay inputs."""
    pinned = require_profile(profile)
    policy_id = pinned["compatibility_policy"]["policy_id"]
    key = replay_key or compute_replay_key(
        source_manifest_digest=source_manifest_digest,
        profile_digest=pinned["profile_digest"],
        mode=mode,
        policy_id=policy_id,
    )
    if replay_key is not None:
        expected = compute_replay_key(
            source_manifest_digest=source_manifest_digest,
            profile_digest=pinned["profile_digest"],
            mode=mode,
            policy_id=policy_id,
        )
        if key != expected:
            return {"error": "replay_input_mismatch", "expected_replay_key": expected}

    existing = store.get(key, mode)
    if existing is not None:
        return {
            "mode": mode,
            "replay_key": key,
            "reused": True,
            "output": existing,
        }

    output = dict(producer())
    try:
        sealed = store.seal(key, mode, output)
    except MigrationRunError as error:
        return {"error": str(error), "replay_key": key, "mode": mode}

    return {
        "mode": mode,
        "replay_key": key,
        "reused": False,
        "output": sealed,
    }


def seal_analyze(
    store: MigrationRunStore,
    *,
    profile: Mapping[str, Any],
    source_manifest_digest: str,
    findings: list[Mapping[str, Any]],
) -> dict[str, Any]:
    return run_stage(
        store,
        profile=profile,
        source_manifest_digest=source_manifest_digest,
        mode="analyze",
        producer=lambda: build_analysis(
            source_manifest_digest=source_manifest_digest,
            findings=findings,
        ),
    )


def seal_plan(
    store: MigrationRunStore,
    *,
    profile: Mapping[str, Any],
    source_manifest_digest: str,
    analysis: Mapping[str, Any],
    planned_ops: list[Mapping[str, Any]],
) -> dict[str, Any]:
    pinned = require_profile(profile)
    if analysis["source_manifest_digest"] != source_manifest_digest:
        return {"error": "source_manifest_mismatch"}
    return run_stage(
        store,
        profile=profile,
        source_manifest_digest=source_manifest_digest,
        mode="plan",
        producer=lambda: build_plan(
            analysis_digest=str(analysis["analysis_digest"]),
            profile_digest=pinned["profile_digest"],
            policy_id=pinned["compatibility_policy"]["policy_id"],
            planned_ops=planned_ops,
        ),
    )


def seal_apply(
    store: MigrationRunStore,
    *,
    profile: Mapping[str, Any],
    source_manifest_digest: str,
    plan: Mapping[str, Any],
    patch_digest: str,
    file_entries: list[Mapping[str, Any]],
    mapping_digest: str,
    warnings: list[str] | None = None,
    plan_digest: str | None = None,
) -> dict[str, Any]:
    pinned = require_profile(profile)
    expected_plan_digest = plan_digest or str(plan["plan_digest"])
    if expected_plan_digest != plan["plan_digest"]:
        return {"error": "plan_digest_mismatch", "expected": plan["plan_digest"]}
    if plan["profile_digest"] != pinned["profile_digest"]:
        return {"error": "profile_digest_mismatch"}
    return run_stage(
        store,
        profile=profile,
        source_manifest_digest=source_manifest_digest,
        mode="apply",
        producer=lambda: build_change_bundle(
            plan_digest=expected_plan_digest,
            patch_digest=patch_digest,
            file_entries=file_entries,
            mapping_digest=mapping_digest,
            warnings=warnings,
        ),
    )


def seal_validate(
    store: MigrationRunStore,
    *,
    profile: Mapping[str, Any],
    source_manifest_digest: str,
    bundle: Mapping[str, Any],
    passed: bool,
    findings: list[Mapping[str, Any]],
    diagnostics_digest: str,
) -> dict[str, Any]:
    pinned = require_profile(profile)
    return run_stage(
        store,
        profile=profile,
        source_manifest_digest=source_manifest_digest,
        mode="validate",
        producer=lambda: build_validation(
            bundle_digest=str(bundle["bundle_digest"]),
            validator=pinned["validator"],
            passed=passed,
            findings=findings,
            diagnostics_digest=diagnostics_digest,
        ),
    )


def build_status_payload(
    profile: Mapping[str, Any],
    *,
    mode: str,
    replay_key: str,
    source_manifest_digest: str,
    stage_outputs: Mapping[str, Mapping[str, Any] | None],
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a run status payload that omits private source bytes by default."""
    pinned = require_profile(profile)
    payload: dict[str, Any] = {
        "schema_version": "migration-run-status/v1",
        "profile_id": pinned["profile_id"],
        "profile_version": pinned["version"],
        "profile_digest": pinned["profile_digest"],
        "source": dict(pinned["source"]),
        "target": dict(pinned["target"]),
        "mode": mode,
        "replay_key": replay_key,
        "source_manifest_digest": source_manifest_digest,
        "policy_id": pinned["compatibility_policy"]["policy_id"],
    }
    for stage_mode, output in stage_outputs.items():
        if output is None:
            continue
        digest_field = STAGE_DIGEST_FIELDS[stage_mode]
        payload[digest_field] = output[digest_field]
    if extra:
        for key, value in extra.items():
            if key in PRIVATE_STATUS_KEYS:
                continue
            payload[key] = value
    return redact_payload(payload, pinned["retention_redaction"])


def build_receipt_fields(
    profile: Mapping[str, Any],
    *,
    mode: str,
    replay_key: str,
    source_manifest_digest: str,
    stage_outputs: Mapping[str, Mapping[str, Any] | None],
    validation_passed: bool | None = None,
) -> dict[str, Any]:
    """Partial composite receipt fields for #167; omits private source bytes."""
    pinned = require_profile(profile)
    fields: dict[str, Any] = {
        "schema_version": "migration-receipt/v1",
        "profile_id": pinned["profile_id"],
        "profile_version": pinned["version"],
        "profile_digest": pinned["profile_digest"],
        "source": dict(pinned["source"]),
        "target": dict(pinned["target"]),
        "transformer": dict(pinned["transformer"]),
        "validator": dict(pinned["validator"]),
        "execution_locality": pinned["execution_locality"],
        "mode": mode,
        "source_manifest_digest": source_manifest_digest,
        "replay_key": replay_key,
        "retention_redaction": dict(pinned["retention_redaction"]),
    }
    for stage_mode, output in stage_outputs.items():
        if output is None:
            continue
        digest_field = STAGE_DIGEST_FIELDS[stage_mode]
        fields[digest_field] = output[digest_field]
    if validation_passed is not None:
        fields["validation_passed"] = validation_passed
    return redact_payload(fields, pinned["retention_redaction"])


def redact_payload(payload: Mapping[str, Any], retention: Mapping[str, Any]) -> dict[str, Any]:
    excludes = set(retention.get("receipt_excludes_by_default", ()))
    redacted: dict[str, Any] = {}
    for key, value in payload.items():
        if key in excludes or key in PRIVATE_STATUS_KEYS:
            continue
        redacted[key] = value
    return redacted


def assert_no_private_bytes(payload: Mapping[str, Any]) -> None:
    for key in payload:
        if key in PRIVATE_STATUS_KEYS:
            raise MigrationRunError(f"private field leaked into payload: {key}")
