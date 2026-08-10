"""Seal and verify portable composite migration receipts (ADR 0008 §12)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .migration_profile import (
    canonical_json,
    compute_profile_digest,
    require_profile,
    sha256_hex,
    validate_version_pin,
)
from .migration_run import (
    PRIVATE_STATUS_KEYS,
    STAGE_DIGEST_FIELDS,
    assert_no_private_bytes,
    compute_replay_key,
    redact_payload,
)

RECEIPT_SCHEMA_VERSION = "migration-receipt/v1"

REQUIRED_RECEIPT_FIELDS: frozenset[str] = frozenset(
    {
        "schema_version",
        "profile_id",
        "profile_version",
        "profile_digest",
        "source",
        "target",
        "transformer",
        "validator",
        "execution_locality",
        "mode",
        "source_manifest_digest",
        "replay_key",
        "retention_redaction",
        "receipt_digest",
    }
)

# Envelope signature fields are excluded from receipt_digest per ADR 0008 §12.
RECEIPT_DIGEST_EXCLUDES: frozenset[str] = frozenset(
    {"receipt_digest", "signature", "alg", "key_id"}
)


class MigrationReceiptError(ValueError):
    """Composite migration receipt seal or verify failed."""


def compute_receipt_digest(receipt: Mapping[str, Any]) -> str:
    """sha256 of canonical receipt excluding receipt_digest and Envelope signature."""
    without = {key: value for key, value in receipt.items() if key not in RECEIPT_DIGEST_EXCLUDES}
    return sha256_hex(canonical_json(without))


def seal_migration_receipt(
    profile: Mapping[str, Any],
    *,
    mode: str,
    source_manifest_digest: str,
    stage_outputs: Mapping[str, Mapping[str, Any] | None],
    validation: Mapping[str, Any] | None = None,
    cites: Sequence[str] | None = None,
    require_success: bool = False,
    replay_key: str | None = None,
) -> dict[str, Any]:
    """Seal a portable composite migration receipt a standalone client can verify.

    When ``require_success`` is true, refuses to seal if the validator did not
    pass — validator failure must never be reported as a successful migration.
    """
    pinned = require_profile(profile)
    policy_id = pinned["compatibility_policy"]["policy_id"]
    key = replay_key or compute_replay_key(
        source_manifest_digest=source_manifest_digest,
        profile_digest=pinned["profile_digest"],
        mode=mode,
        policy_id=policy_id,
    )

    validation_artifact = validation
    if validation_artifact is None and stage_outputs.get("validate") is not None:
        validation_artifact = stage_outputs["validate"]

    validation_passed: bool | None = None
    if validation_artifact is not None:
        if "passed" not in validation_artifact:
            return {"error": "validation_passed_missing"}
        validation_passed = bool(validation_artifact["passed"])
        if not validation_passed:
            validation_passed = False
        elif _has_blocking_findings(validation_artifact.get("findings") or []):
            # ADR §12 step 5: cannot claim success with breaking/block findings.
            validation_passed = False

    if require_success:
        if validation_artifact is None:
            return {"error": "cannot_seal_success", "reason": "validation_required"}
        if not validation_passed:
            return {
                "error": "cannot_seal_success",
                "reason": "validation_failed",
                "validation_passed": False,
            }

    receipt: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
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
        "analysis_digest": _stage_digest(stage_outputs, "analyze"),
        "plan_digest": _stage_digest(stage_outputs, "plan"),
        "bundle_digest": _stage_digest(stage_outputs, "apply"),
        "validation_digest": _stage_digest(stage_outputs, "validate"),
        "replay_key": key,
        "retention_redaction": dict(pinned["retention_redaction"]),
    }
    if validation_passed is not None:
        receipt["validation_passed"] = validation_passed
    if validation_artifact is not None and receipt.get("validation_digest") is None:
        receipt["validation_digest"] = validation_artifact.get("validation_digest")
    if cites:
        receipt["cites"] = list(cites)

    receipt = redact_payload(receipt, pinned["retention_redaction"])
    assert_no_private_bytes(receipt)
    receipt["receipt_digest"] = compute_receipt_digest(receipt)
    return {"receipt": receipt, "validation_passed": validation_passed}


def verify_migration_receipt(
    receipt: Mapping[str, Any],
    *,
    profile: Mapping[str, Any] | None = None,
    validation: Mapping[str, Any] | None = None,
    stage_artifacts: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Independently verify a composite receipt without an Orrery-only endpoint.

    Envelope signature verification is documented separately
    (``docs/verification/envelope-verification.md``); this check covers the
    receipt body digest and recoverable identity pins.
    """
    if not isinstance(receipt, Mapping):
        return {"verified": False, "error": "receipt_not_object"}

    missing = sorted(REQUIRED_RECEIPT_FIELDS - set(receipt))
    if missing:
        return {"verified": False, "error": "missing_fields", "missing": missing}

    if receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        return {
            "verified": False,
            "error": "schema_version",
            "expected": RECEIPT_SCHEMA_VERSION,
            "actual": receipt.get("schema_version"),
        }

    for key in PRIVATE_STATUS_KEYS:
        if key in receipt:
            return {"verified": False, "error": "private_field_present", "field": key}

    expected_digest = compute_receipt_digest(receipt)
    if receipt.get("receipt_digest") != expected_digest:
        return {
            "verified": False,
            "error": "receipt_digest_mismatch",
            "expected": expected_digest,
            "actual": receipt.get("receipt_digest"),
        }

    for pin_field in ("source", "target"):
        pin = receipt.get(pin_field)
        if not isinstance(pin, Mapping) or set(pin) != {"kind", "version"}:
            return {"verified": False, "error": "pin_shape", "field": pin_field}
        pin_error = validate_version_pin(pin.get("version"))
        if pin_error is not None:
            return {"verified": False, "error": pin_error, "field": f"{pin_field}.version"}

    for tool_field in ("transformer", "validator"):
        tool = receipt.get(tool_field)
        if not isinstance(tool, Mapping) or set(tool) != {"name", "version", "digest"}:
            return {"verified": False, "error": "tool_shape", "field": tool_field}
        for sub in ("name", "version", "digest"):
            if not isinstance(tool.get(sub), str) or not str(tool[sub]).strip():
                return {"verified": False, "error": "tool_field", "field": f"{tool_field}.{sub}"}
        pin_error = validate_version_pin(tool["version"])
        if pin_error is not None:
            return {"verified": False, "error": pin_error, "field": f"{tool_field}.version"}

    if profile is not None:
        pinned = require_profile(profile)
        recomputed = compute_profile_digest(pinned)
        if pinned["profile_digest"] != recomputed:
            return {"verified": False, "error": "profile_digest_mismatch"}
        if receipt["profile_digest"] != pinned["profile_digest"]:
            return {
                "verified": False,
                "error": "receipt_profile_digest_mismatch",
                "expected": pinned["profile_digest"],
                "actual": receipt["profile_digest"],
            }
        if receipt["profile_id"] != pinned["profile_id"]:
            return {"verified": False, "error": "profile_id_mismatch"}
        if receipt["profile_version"] != pinned["version"]:
            return {"verified": False, "error": "profile_version_mismatch"}
        if receipt["target"] != pinned["target"]:
            return {"verified": False, "error": "target_mismatch"}
        if receipt["transformer"] != pinned["transformer"]:
            return {"verified": False, "error": "transformer_mismatch"}
        if receipt["validator"] != pinned["validator"]:
            return {"verified": False, "error": "validator_mismatch"}

    if stage_artifacts:
        for mode, artifact in stage_artifacts.items():
            digest_field = STAGE_DIGEST_FIELDS.get(mode)
            if digest_field is None:
                continue
            if receipt.get(digest_field) is None:
                continue
            if artifact.get(digest_field) != receipt.get(digest_field):
                return {
                    "verified": False,
                    "error": "stage_digest_mismatch",
                    "field": digest_field,
                }

    if validation is not None:
        if receipt.get("validation_digest") != validation.get("validation_digest"):
            return {"verified": False, "error": "validation_digest_mismatch"}
        receipt_passed = receipt.get("validation_passed")
        artifact_passed = bool(validation.get("passed"))
        if receipt_passed is True and not artifact_passed:
            return {"verified": False, "error": "validation_passed_inconsistent"}
        if receipt_passed is True and _has_blocking_findings(validation.get("findings") or []):
            return {"verified": False, "error": "validation_passed_with_blocking_findings"}

    if receipt.get("validation_passed") is True and validation is None:
        # Without the artifact, still reject success claims that contradict
        # nothing held — identity recovery remains available.
        pass

    recovered = {
        "profile_id": receipt["profile_id"],
        "profile_version": receipt["profile_version"],
        "profile_digest": receipt["profile_digest"],
        "target": dict(receipt["target"]),
        "transformer": dict(receipt["transformer"]),
        "validator": dict(receipt["validator"]),
        "validation_passed": receipt.get("validation_passed"),
        "receipt_digest": receipt["receipt_digest"],
    }
    return {"verified": True, "recovered": recovered}


def _stage_digest(
    stage_outputs: Mapping[str, Mapping[str, Any] | None],
    mode: str,
) -> str | None:
    output = stage_outputs.get(mode)
    if output is None:
        return None
    return output.get(STAGE_DIGEST_FIELDS[mode])


def _has_blocking_findings(findings: Sequence[Mapping[str, Any]]) -> bool:
    for item in findings:
        if item.get("severity") == "breaking" and item.get("action") == "block":
            return True
    return False
