"""Validate migration change bundles under a pinned target profile (ADR 0008)."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from .migration_profile import canonical_json, require_profile, sha256_hex, validate_version_pin
from .migration_run import (
    PRIVATE_STATUS_KEYS,
    MigrationRunStore,
    build_validation,
    seal_validate,
)

PRIVATE_DIAGNOSTIC_KEYS = PRIVATE_STATUS_KEYS | frozenset(
    {
        "raw_source",
        "source_text",
        "source",
        "patch",
        "diff",
    }
)


class MigrationValidateError(ValueError):
    """Validator adapter failed closed."""


def redact_diagnostics(
    diagnostics: Mapping[str, Any] | Sequence[Any] | str | None,
    retention: Mapping[str, Any],
) -> tuple[dict[str, Any], str]:
    """Bound and redact diagnostics; never retain raw source by default.

    Returns ``(safe_diagnostics, diagnostics_digest)``.
    """
    max_bytes = int(retention.get("max_diagnostics_bytes", 65536))
    max_finding_msg = int(retention.get("max_finding_message_bytes", 512))
    excludes = set(retention.get("receipt_excludes_by_default", ())) | PRIVATE_DIAGNOSTIC_KEYS

    if diagnostics is None:
        safe: dict[str, Any] = {"entries": [], "truncated": False, "redacted_keys": []}
    elif isinstance(diagnostics, str):
        text = _truncate_utf8(diagnostics, max_bytes)
        safe = {
            "entries": [{"message": _truncate_utf8(text, max_finding_msg)}],
            "truncated": len(diagnostics.encode("utf-8")) > max_bytes,
            "redacted_keys": [],
        }
    elif isinstance(diagnostics, Sequence) and not isinstance(diagnostics, (str, bytes)):
        entries, redacted_keys, truncated = _redact_entries(
            list(diagnostics), excludes=excludes, max_finding_msg=max_finding_msg
        )
        safe = {"entries": entries, "truncated": truncated, "redacted_keys": sorted(redacted_keys)}
        encoded = canonical_json(safe)
        if len(encoded) > max_bytes:
            safe = {
                "entries": entries[: max(1, len(entries) // 2)],
                "truncated": True,
                "redacted_keys": sorted(redacted_keys),
            }
    elif isinstance(diagnostics, Mapping):
        cleaned, redacted_keys = _redact_mapping(diagnostics, excludes=excludes)
        if "message" in cleaned and isinstance(cleaned["message"], str):
            cleaned["message"] = _truncate_utf8(cleaned["message"], max_finding_msg)
        safe = {
            "summary": cleaned,
            "truncated": False,
            "redacted_keys": sorted(redacted_keys),
        }
        encoded = canonical_json(safe)
        if len(encoded) > max_bytes:
            safe = {
                "summary": {"note": "diagnostics_truncated"},
                "truncated": True,
                "redacted_keys": sorted(redacted_keys),
            }
    else:
        raise MigrationValidateError("diagnostics_invalid_type")

    digest = sha256_hex(canonical_json(safe))
    return safe, digest


def bound_findings(
    findings: Sequence[Mapping[str, Any]],
    retention: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Copy findings with bounded messages and private keys stripped."""
    max_msg = int(retention.get("max_finding_message_bytes", 512))
    excludes = set(retention.get("receipt_excludes_by_default", ())) | PRIVATE_DIAGNOSTIC_KEYS
    bound: list[dict[str, Any]] = []
    for item in findings:
        entry = {key: value for key, value in item.items() if key not in excludes}
        if "message" in entry and isinstance(entry["message"], str):
            entry["message"] = _truncate_utf8(entry["message"], max_msg)
        bound.append(entry)
    return bound


def evaluation_passed(
    findings: Sequence[Mapping[str, Any]],
    *,
    checker_passed: bool | None = None,
) -> bool:
    """Return whether validation may report success.

    Any finding with ``severity: breaking`` and ``action: block`` forces failure.
    An explicit ``checker_passed=False`` also forces failure.
    """
    if checker_passed is False:
        return False
    for item in findings:
        if item.get("severity") == "breaking" and item.get("action") == "block":
            return False
    if checker_passed is True:
        return True
    return True


def validate_change_bundle(
    profile: Mapping[str, Any],
    bundle: Mapping[str, Any],
    *,
    findings: Sequence[Mapping[str, Any]] | None = None,
    diagnostics: Mapping[str, Any] | Sequence[Any] | str | None = None,
    checker: Callable[[Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]] | None = None,
    checker_passed: bool | None = None,
) -> dict[str, Any]:
    """Validate a change bundle under a pinned profile; seal a validation artifact.

    Does not report validator failure as a successful migration: ``passed`` is
    false whenever the checker fails or blocking findings are present.
    """
    pinned = require_profile(profile)
    if "bundle_digest" not in bundle:
        return {"error": "bundle_digest_required"}

    pin_error = validate_version_pin(pinned["target"]["version"])
    if pin_error is not None:
        return {"error": pin_error, "field": "target.version"}

    for tool_field in ("transformer", "validator"):
        tool = pinned[tool_field]
        tool_pin = validate_version_pin(tool["version"])
        if tool_pin is not None:
            return {"error": tool_pin, "field": f"{tool_field}.version"}

    collected: list[Mapping[str, Any]] = list(findings or [])
    effective_passed = checker_passed
    raw_diagnostics = diagnostics

    if checker is not None:
        result = dict(checker(pinned, bundle))
        if "error" in result and "passed" not in result:
            return {"error": "checker_error", "detail": result["error"]}
        if "findings" in result and isinstance(result["findings"], list):
            collected.extend(result["findings"])
        if "diagnostics" in result and raw_diagnostics is None:
            raw_diagnostics = result["diagnostics"]
        if "passed" in result:
            effective_passed = bool(result["passed"])

    retention = pinned["retention_redaction"]
    safe_findings = bound_findings(collected, retention)
    safe_diagnostics, diagnostics_digest = redact_diagnostics(raw_diagnostics, retention)

    # Fail closed: never claim success when blocking findings or checker fail.
    passed = evaluation_passed(safe_findings, checker_passed=effective_passed)
    if any(key in safe_diagnostics for key in PRIVATE_DIAGNOSTIC_KEYS):
        raise MigrationValidateError("diagnostics_leaked_private_keys")

    validation = build_validation(
        bundle_digest=str(bundle["bundle_digest"]),
        validator=pinned["validator"],
        passed=passed,
        findings=safe_findings,
        diagnostics_digest=diagnostics_digest,
    )
    return {
        "validation": validation,
        "diagnostics": safe_diagnostics,
        "validation_passed": passed,
        "profile_id": pinned["profile_id"],
        "profile_version": pinned["version"],
        "profile_digest": pinned["profile_digest"],
        "target": dict(pinned["target"]),
        "validator": dict(pinned["validator"]),
    }


def run_validate_stage(
    store: MigrationRunStore,
    *,
    profile: Mapping[str, Any],
    source_manifest_digest: str,
    bundle: Mapping[str, Any],
    findings: Sequence[Mapping[str, Any]] | None = None,
    diagnostics: Mapping[str, Any] | Sequence[Any] | str | None = None,
    checker: Callable[[Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]] | None = None,
    checker_passed: bool | None = None,
) -> dict[str, Any]:
    """Validate then persist the validation stage via :func:`seal_validate`."""
    adapter = validate_change_bundle(
        profile,
        bundle,
        findings=findings,
        diagnostics=diagnostics,
        checker=checker,
        checker_passed=checker_passed,
    )
    if "error" in adapter:
        return adapter

    validation = adapter["validation"]
    sealed = seal_validate(
        store,
        profile=profile,
        source_manifest_digest=source_manifest_digest,
        bundle=bundle,
        passed=bool(validation["passed"]),
        findings=list(validation["findings"]),
        diagnostics_digest=str(validation["diagnostics_digest"]),
    )
    if "error" in sealed:
        return sealed
    return {
        **sealed,
        "validation_passed": adapter["validation_passed"],
        "diagnostics": adapter["diagnostics"],
    }


def _truncate_utf8(text: str, max_bytes: int) -> str:
    if max_bytes <= 0:
        return ""
    raw = text.encode("utf-8")
    if len(raw) <= max_bytes:
        return text
    ellipsis = "…"
    ellipsis_bytes = ellipsis.encode("utf-8")
    if max_bytes <= len(ellipsis_bytes):
        return ellipsis_bytes[:max_bytes].decode("utf-8", errors="ignore") or ""
    budget = max_bytes - len(ellipsis_bytes)
    clipped = raw[:budget]
    while clipped:
        try:
            return clipped.decode("utf-8") + ellipsis
        except UnicodeDecodeError:
            clipped = clipped[:-1]
    return ellipsis


def _redact_mapping(
    value: Mapping[str, Any],
    *,
    excludes: set[str],
) -> tuple[dict[str, Any], set[str]]:
    cleaned: dict[str, Any] = {}
    redacted: set[str] = set()
    for key, item in value.items():
        if key in excludes:
            redacted.add(str(key))
            continue
        if isinstance(item, Mapping):
            nested, nested_redacted = _redact_mapping(item, excludes=excludes)
            cleaned[str(key)] = nested
            redacted |= nested_redacted
        else:
            cleaned[str(key)] = item
    return cleaned, redacted


def _redact_entries(
    entries: list[Any],
    *,
    excludes: set[str],
    max_finding_msg: int,
) -> tuple[list[Any], set[str], bool]:
    redacted: set[str] = set()
    truncated = False
    out: list[Any] = []
    for entry in entries:
        if isinstance(entry, Mapping):
            cleaned, keys = _redact_mapping(entry, excludes=excludes)
            redacted |= keys
            if "message" in cleaned and isinstance(cleaned["message"], str):
                original = cleaned["message"]
                cleaned["message"] = _truncate_utf8(original, max_finding_msg)
                if cleaned["message"] != original:
                    truncated = True
            out.append(cleaned)
        elif isinstance(entry, str):
            clipped = _truncate_utf8(entry, max_finding_msg)
            if clipped != entry:
                truncated = True
            out.append(clipped)
        else:
            out.append(entry)
    return out, redacted, truncated
