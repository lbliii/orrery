"""Deterministic OpenAPI inventory per ADR 0008 analyze-stage fields (#174)."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any

from .contract import (
    FEATURE_CLASSES,
    MAX_ENTRIES,
    MAX_ENTRY_BYTES,
    MAX_FINDINGS,
    MAX_MESSAGE_BYTES,
    REF_POLICY_MODES,
    RefPolicyMode,
)
from .parser import RawFinding, scan_documents


def inventory(
    entries: Sequence[Mapping[str, Any]] | None = None,
    ref_policy: Mapping[str, Any] | None = None,
) -> dict[str, object]:
    """Build a digest-bound inventory for bounded OpenAPI document entries."""
    if entries is None:
        return {"error": "entries_required"}
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        return {"error": "entries_invalid"}

    policy_error = _normalize_ref_policy(ref_policy)
    if isinstance(policy_error, dict) and "error" in policy_error:
        return policy_error
    ref_mode, allowed_prefixes = policy_error  # type: ignore[misc]

    normalized_entries: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    for item in entries:
        if not isinstance(item, Mapping):
            return {"error": "entry_invalid"}
        path = item.get("path")
        content = item.get("content")
        if not isinstance(path, str) or not path.strip():
            return {"error": "path_invalid", "path": path}
        if not isinstance(content, str):
            return {"error": "content_invalid", "path": path}
        if path in seen_paths:
            return {"error": "path_duplicate", "path": path}
        content_bytes = unicodedata.normalize("NFC", content).encode("utf-8")
        if len(content_bytes) > MAX_ENTRY_BYTES:
            return {"error": "content_too_large", "path": path}
        seen_paths.add(path)
        normalized_entries.append({"path": path, "content": content})

    if not normalized_entries:
        return {"error": "entries_empty"}
    if len(normalized_entries) > MAX_ENTRIES:
        return {"error": "entries_too_many", "count": len(normalized_entries)}

    normalized_entries.sort(key=lambda entry: entry["path"])
    source_manifest_digest = _digest(
        {"entries": [_manifest_entry(entry) for entry in normalized_entries]}
    )

    scan = scan_documents(
        normalized_entries,
        ref_mode=ref_mode,
        allowed_prefixes=allowed_prefixes,
    )
    findings = [_serialize_finding(raw) for raw in scan.findings]
    findings.sort(key=_finding_sort_key)
    truncated = len(findings) > MAX_FINDINGS
    if truncated:
        findings = findings[:MAX_FINDINGS]

    inventory_body: dict[str, object] = {
        "source_manifest_digest": source_manifest_digest,
        "findings": findings,
        "findings_truncated": truncated,
    }
    if scan.source is not None:
        inventory_body["source"] = {
            "kind": scan.source["kind"],
            "version": scan.source["version"],
        }

    inventory_digest = _digest(inventory_body)
    return {
        **inventory_body,
        "inventory_digest": inventory_digest,
        "analysis_digest": inventory_digest,
        "entry_count": len(normalized_entries),
        "finding_count": len(findings),
        "ref_policy": {"mode": ref_mode, "allowed_prefixes": list(allowed_prefixes)},
    }


def verify_inventory(payload: Mapping[str, Any]) -> dict[str, object]:
    """Recompute digests for an inventory payload."""
    required = ("source_manifest_digest", "findings", "inventory_digest")
    missing = [key for key in required if key not in payload]
    if missing:
        return {"verified": False, "error": "missing_fields", "missing": missing}

    findings = payload["findings"]
    if not isinstance(findings, list):
        return {"verified": False, "error": "findings_invalid"}

    for item in findings:
        if not isinstance(item, Mapping):
            return {"verified": False, "error": "finding_invalid"}
        if item.get("class") not in FEATURE_CLASSES:
            return {"verified": False, "error": "class_invalid", "class": item.get("class")}
        expected = item.get("finding_digest")
        if not isinstance(expected, str):
            return {"verified": False, "error": "finding_digest_invalid"}
        recomputed = _finding_digest(item)
        if recomputed != expected:
            return {
                "verified": False,
                "error": "finding_digest_mismatch",
                "expected": recomputed,
                "received": expected,
            }

    body: dict[str, object] = {
        "source_manifest_digest": payload["source_manifest_digest"],
        "findings": sorted(findings, key=_finding_sort_key),
        "findings_truncated": bool(payload.get("findings_truncated", False)),
    }
    source = payload.get("source")
    if isinstance(source, Mapping) and "kind" in source and "version" in source:
        body["source"] = {"kind": source["kind"], "version": source["version"]}

    expected_inventory = _digest(body)
    if payload["inventory_digest"] != expected_inventory:
        return {
            "verified": False,
            "error": "inventory_digest_mismatch",
            "expected": expected_inventory,
            "received": payload["inventory_digest"],
        }
    return {"verified": True}


def canonical_json_bytes(value: Any) -> bytes:
    """ADR 0008 canonical JSON: sorted keys, compact separators, NFC strings."""
    return json.dumps(
        _nfc_normalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _normalize_ref_policy(
    ref_policy: Mapping[str, Any] | None,
) -> tuple[RefPolicyMode, tuple[str, ...]] | dict[str, object]:
    if ref_policy is None:
        return "deny_external", ()
    if not isinstance(ref_policy, Mapping):
        return {"error": "ref_policy_invalid"}
    mode = ref_policy.get("mode", "deny_external")
    if mode not in REF_POLICY_MODES:
        return {"error": "ref_policy_mode_invalid", "mode": mode}
    prefixes_raw = ref_policy.get("allowed_prefixes", [])
    if prefixes_raw is None:
        prefixes_raw = []
    if not isinstance(prefixes_raw, Sequence) or isinstance(prefixes_raw, (str, bytes)):
        return {"error": "ref_policy_prefixes_invalid"}
    prefixes: list[str] = []
    for item in prefixes_raw:
        if not isinstance(item, str) or not item.strip():
            return {"error": "ref_policy_prefix_invalid"}
        prefixes.append(item.strip())
    if mode == "allow_prefixes" and not prefixes:
        return {"error": "ref_policy_prefixes_required"}
    if mode == "deny_external" and prefixes:
        return {"error": "ref_policy_prefixes_not_allowed"}
    return mode, tuple(prefixes)  # type: ignore[return-value]


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


def _manifest_entry(entry: Mapping[str, str]) -> dict[str, str]:
    content = unicodedata.normalize("NFC", entry["content"])
    return {
        "path": entry["path"],
        "content_digest": hashlib.sha256(content.encode("utf-8")).hexdigest(),
    }


def _serialize_finding(raw: RawFinding) -> dict[str, object]:
    payload: dict[str, object] = {
        "feature_id": raw.feature_id,
        "class": raw.class_,
        "path": raw.path,
        "span": {"line": raw.line, "column": raw.column},
    }
    if raw.message:
        message = unicodedata.normalize("NFC", raw.message)
        if len(message.encode("utf-8")) > MAX_MESSAGE_BYTES:
            message = message.encode("utf-8")[:MAX_MESSAGE_BYTES].decode("utf-8", "ignore")
        payload["message"] = message
    payload["finding_digest"] = _finding_digest(payload)
    return payload


def _finding_digest(finding: Mapping[str, Any]) -> str:
    body = {
        "feature_id": finding["feature_id"],
        "class": finding["class"],
        "path": finding["path"],
    }
    span = finding.get("span")
    if isinstance(span, Mapping):
        body["span"] = {"column": span["column"], "line": span["line"]}
    message = finding.get("message")
    if isinstance(message, str) and message:
        body["message"] = message
    return _digest(body)


def _finding_sort_key(finding: Mapping[str, Any]) -> tuple[Any, ...]:
    span = finding.get("span") if isinstance(finding.get("span"), Mapping) else {}
    return (
        finding.get("path", ""),
        span.get("line", 0),
        span.get("column", 0),
        finding.get("feature_id", ""),
        finding.get("class", ""),
    )
