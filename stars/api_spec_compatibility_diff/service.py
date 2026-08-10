"""Compatibility diff under ADR 0008 compatibility_policy (#176)."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any

from stars.api_spec_openapi_inventory.service import inventory as build_inventory

from .contract import (
    CHANGE_CLASSIFICATIONS,
    MAX_CHANGES,
    MAX_ENTRIES,
    MAX_ENTRY_BYTES,
    MAX_MESSAGE_BYTES,
    POLICY_ACTIONS,
    POLICY_SEVERITIES,
    RULE_PATH_ADD,
    RULE_SCHEMA_ADD,
    ChangeClassification,
    PolicyAction,
    PolicySeverity,
)
from .diff import RawChange, compare_surfaces, extract_surface, parse_document


def compatibility_diff(
    source_entries: Sequence[Mapping[str, Any]] | None = None,
    target_entries: Sequence[Mapping[str, Any]] | None = None,
    compatibility_policy: Mapping[str, Any] | None = None,
) -> dict[str, object]:
    """Compare source vs target OpenAPI entries under a declared policy."""
    source_normalized, source_error = _normalize_entries(source_entries, label="source")
    if source_error is not None:
        return source_error
    target_normalized, target_error = _normalize_entries(target_entries, label="target")
    if target_error is not None:
        return target_error
    policy, policy_error = _normalize_policy(compatibility_policy)
    if policy_error is not None:
        return policy_error
    assert source_normalized is not None and target_normalized is not None
    assert policy is not None

    source_inventory = build_inventory(source_normalized)
    if "error" in source_inventory:
        return {
            "error": "source_inventory_failed",
            "detail": dict(source_inventory),
        }
    target_inventory = build_inventory(target_normalized)
    if "error" in target_inventory:
        return {
            "error": "target_inventory_failed",
            "detail": dict(target_inventory),
        }

    rule_index = {str(rule["id"]): rule for rule in policy["rules"]}
    raw_changes = _diff_entries(source_normalized, target_normalized)
    changes = [
        _classify_change(raw, rule_index=rule_index, default_action=policy["default_action"])
        for raw in raw_changes
    ]
    changes.sort(key=_change_sort_key)
    truncated = len(changes) > MAX_CHANGES
    if truncated:
        changes = changes[:MAX_CHANGES]

    policy_digest = _digest(policy)
    body: dict[str, object] = {
        "policy_id": policy["policy_id"],
        "policy_digest": policy_digest,
        "source_manifest_digest": source_inventory["source_manifest_digest"],
        "target_manifest_digest": target_inventory["source_manifest_digest"],
        "source_analysis_digest": source_inventory["analysis_digest"],
        "target_analysis_digest": target_inventory["analysis_digest"],
        "changes": changes,
        "changes_truncated": truncated,
        "runtime_compatibility_claimed": False,
    }
    diff_digest = _digest(body)
    return {
        **body,
        "diff_digest": diff_digest,
        "change_count": len(changes),
        "source_entry_count": len(source_normalized),
        "target_entry_count": len(target_normalized),
        "compatibility_policy": {
            "policy_id": policy["policy_id"],
            "default_action": policy["default_action"],
            "rules": list(policy["rules"]),
        },
    }


def verify_diff(payload: Mapping[str, Any]) -> dict[str, object]:
    """Recompute diff_digest for a sealed compatibility-diff payload."""
    required = (
        "policy_id",
        "policy_digest",
        "source_manifest_digest",
        "target_manifest_digest",
        "source_analysis_digest",
        "target_analysis_digest",
        "changes",
        "changes_truncated",
        "runtime_compatibility_claimed",
        "diff_digest",
    )
    missing = [key for key in required if key not in payload]
    if missing:
        return {"verified": False, "error": "missing_fields", "missing": missing}

    changes = payload["changes"]
    if not isinstance(changes, list):
        return {"verified": False, "error": "changes_invalid"}
    for item in changes:
        if not isinstance(item, Mapping):
            return {"verified": False, "error": "change_invalid"}
        if item.get("classification") not in CHANGE_CLASSIFICATIONS:
            return {
                "verified": False,
                "error": "classification_invalid",
                "classification": item.get("classification"),
            }
        expected = item.get("change_digest")
        if not isinstance(expected, str):
            return {"verified": False, "error": "change_digest_invalid"}
        if _change_digest(item) != expected:
            return {
                "verified": False,
                "error": "change_digest_mismatch",
                "expected": _change_digest(item),
                "received": expected,
            }

    body: dict[str, object] = {
        "policy_id": payload["policy_id"],
        "policy_digest": payload["policy_digest"],
        "source_manifest_digest": payload["source_manifest_digest"],
        "target_manifest_digest": payload["target_manifest_digest"],
        "source_analysis_digest": payload["source_analysis_digest"],
        "target_analysis_digest": payload["target_analysis_digest"],
        "changes": sorted(changes, key=_change_sort_key),
        "changes_truncated": bool(payload.get("changes_truncated", False)),
        "runtime_compatibility_claimed": bool(payload["runtime_compatibility_claimed"]),
    }
    expected_digest = _digest(body)
    if payload["diff_digest"] != expected_digest:
        return {
            "verified": False,
            "error": "diff_digest_mismatch",
            "expected": expected_digest,
            "received": payload["diff_digest"],
        }
    if payload["runtime_compatibility_claimed"] is not False:
        return {"verified": False, "error": "runtime_claim_forbidden"}
    return {"verified": True}


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        _nfc_normalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _diff_entries(
    source_entries: Sequence[Mapping[str, str]],
    target_entries: Sequence[Mapping[str, str]],
) -> list[RawChange]:
    source_by_path = {entry["path"]: entry["content"] for entry in source_entries}
    target_by_path = {entry["path"]: entry["content"] for entry in target_entries}
    changes: list[RawChange] = []

    for path in sorted(set(source_by_path) | set(target_by_path)):
        source_content = source_by_path.get(path)
        target_content = target_by_path.get(path)
        if source_content is None:
            # Whole document added — treat as additive path surface when parseable.
            document = parse_document(target_content or "")
            if document is None:
                changes.append(
                    RawChange(
                        rule_id="unknown.document.add",
                        kind="add",
                        location=path,
                        location_kind="document",
                        evidence={"document_path": path, "reason": "target_unparseable"},
                    )
                )
                continue
            surface = extract_surface(document)
            empty = {
                "operations": {},
                "schemas": {},
                "info": {},
                "openapi": None,
            }
            changes.extend(compare_surfaces(empty, surface, document_path=path))
            continue
        if target_content is None:
            document = parse_document(source_content)
            if document is None:
                changes.append(
                    RawChange(
                        rule_id="unknown.document.remove",
                        kind="remove",
                        location=path,
                        location_kind="document",
                        evidence={"document_path": path, "reason": "source_unparseable"},
                    )
                )
                continue
            surface = extract_surface(document)
            empty = {
                "operations": {},
                "schemas": {},
                "info": {},
                "openapi": None,
            }
            changes.extend(compare_surfaces(surface, empty, document_path=path))
            continue

        source_doc = parse_document(source_content)
        target_doc = parse_document(target_content)
        if source_doc is None or target_doc is None:
            changes.append(
                RawChange(
                    rule_id="unknown.document.malformed",
                    kind="modify",
                    location=path,
                    location_kind="document",
                    evidence={
                        "document_path": path,
                        "source_parseable": source_doc is not None,
                        "target_parseable": target_doc is not None,
                    },
                )
            )
            continue
        changes.extend(
            compare_surfaces(
                extract_surface(source_doc),
                extract_surface(target_doc),
                document_path=path,
            )
        )
    return changes


def _classify_change(
    raw: RawChange,
    *,
    rule_index: Mapping[str, Mapping[str, Any]],
    default_action: PolicyAction,
) -> dict[str, object]:
    matched = rule_index.get(raw.rule_id)
    if matched is not None:
        severity = matched["severity"]
        action = matched["action"]
        classification = _classification_from_rule(
            severity=severity,  # type: ignore[arg-type]
            action=action,  # type: ignore[arg-type]
            rule_id=raw.rule_id,
        )
        rule_id = str(matched["id"])
    else:
        classification, action = _default_classification(raw.rule_id, default_action)
        severity = None
        rule_id = raw.rule_id

    message = _message_for(raw, classification=classification, action=action)
    payload: dict[str, object] = {
        "rule_id": rule_id,
        "classification": classification,
        "action": action,
        "kind": raw.kind,
        "location": raw.location,
        "location_kind": raw.location_kind,
        "evidence": dict(raw.evidence),
        "message": message,
    }
    if severity is not None:
        payload["policy_severity"] = severity
    payload["change_digest"] = _change_digest(payload)
    return payload


def _classification_from_rule(
    *,
    severity: PolicySeverity,
    action: PolicyAction,
    rule_id: str,
) -> ChangeClassification:
    if action == "allow":
        return "policy-exempt"
    if rule_id in {RULE_PATH_ADD, RULE_SCHEMA_ADD}:
        return "additive"
    if severity in {"breaking", "behavioral", "informational"}:
        return severity
    return "unknown"


def _default_classification(
    rule_id: str,
    default_action: PolicyAction,
) -> tuple[ChangeClassification, PolicyAction]:
    if rule_id in {RULE_PATH_ADD, RULE_SCHEMA_ADD} or rule_id.startswith("additive."):
        return "additive", "allow" if default_action == "allow" else "report"
    if rule_id.startswith("breaking."):
        action: PolicyAction = "block" if default_action == "allow" else default_action
        return "breaking", action
    if rule_id.startswith("info."):
        return "informational", default_action
    # Ambiguous structural edits / unparseable docs without an explicit rule.
    return "unknown", "decision_required"


def _message_for(
    raw: RawChange,
    *,
    classification: ChangeClassification,
    action: PolicyAction,
) -> str:
    text = (
        f"{classification} {raw.kind} at {raw.location} "
        f"(rule={raw.rule_id}, action={action}); "
        "structural equality does not imply runtime compatibility"
    )
    text = unicodedata.normalize("NFC", text)
    if len(text.encode("utf-8")) > MAX_MESSAGE_BYTES:
        text = text.encode("utf-8")[:MAX_MESSAGE_BYTES].decode("utf-8", "ignore")
    return text


def _normalize_policy(
    policy: Mapping[str, Any] | None,
) -> tuple[dict[str, Any] | None, dict[str, object] | None]:
    if policy is None:
        return None, {"error": "compatibility_policy_required"}
    if not isinstance(policy, Mapping):
        return None, {"error": "compatibility_policy_invalid"}
    required = {"policy_id", "default_action", "rules"}
    if set(policy) != required:
        return None, {"error": "compatibility_policy_shape_invalid"}
    policy_id = policy.get("policy_id")
    if not isinstance(policy_id, str) or not policy_id.strip():
        return None, {"error": "policy_id_invalid"}
    default_action = policy.get("default_action")
    if default_action not in POLICY_ACTIONS:
        return None, {"error": "default_action_invalid", "value": default_action}
    rules_raw = policy.get("rules")
    if not isinstance(rules_raw, list):
        return None, {"error": "rules_invalid"}
    rules: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, rule in enumerate(rules_raw):
        if not isinstance(rule, Mapping):
            return None, {"error": "rule_invalid", "index": index}
        if set(rule) != {"id", "severity", "action"}:
            return None, {"error": "rule_shape_invalid", "index": index}
        rule_id = rule.get("id")
        severity = rule.get("severity")
        action = rule.get("action")
        if not isinstance(rule_id, str) or not rule_id.strip():
            return None, {"error": "rule_id_invalid", "index": index}
        if severity not in POLICY_SEVERITIES:
            return None, {"error": "rule_severity_invalid", "index": index}
        if action not in POLICY_ACTIONS:
            return None, {"error": "rule_action_invalid", "index": index}
        if rule_id in seen:
            return None, {"error": "rule_id_duplicate", "id": rule_id}
        seen.add(rule_id)
        rules.append({"id": rule_id, "severity": str(severity), "action": str(action)})
    return {
        "policy_id": policy_id.strip(),
        "default_action": str(default_action),
        "rules": rules,
    }, None


def _normalize_entries(
    entries: Sequence[Mapping[str, Any]] | None,
    *,
    label: str,
) -> tuple[list[dict[str, str]] | None, dict[str, object] | None]:
    if entries is None:
        return None, {"error": f"{label}_entries_required"}
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        return None, {"error": f"{label}_entries_invalid"}

    normalized: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    for item in entries:
        if not isinstance(item, Mapping):
            return None, {"error": f"{label}_entry_invalid"}
        path = item.get("path")
        content = item.get("content")
        if not isinstance(path, str) or not path.strip():
            return None, {"error": f"{label}_path_invalid", "path": path}
        if not isinstance(content, str):
            return None, {"error": f"{label}_content_invalid", "path": path}
        if path in seen_paths:
            return None, {"error": f"{label}_path_duplicate", "path": path}
        content_bytes = unicodedata.normalize("NFC", content).encode("utf-8")
        if len(content_bytes) > MAX_ENTRY_BYTES:
            return None, {"error": f"{label}_content_too_large", "path": path}
        if len(path.encode("utf-8")) > MAX_MESSAGE_BYTES:
            return None, {"error": f"{label}_path_too_long", "path": path}
        seen_paths.add(path)
        normalized.append({"path": path, "content": content})

    if not normalized:
        return None, {"error": f"{label}_entries_empty"}
    if len(normalized) > MAX_ENTRIES:
        return None, {
            "error": f"{label}_entries_too_many",
            "count": len(normalized),
        }
    normalized.sort(key=lambda entry: entry["path"])
    return normalized, None


def _change_digest(change: Mapping[str, Any]) -> str:
    body = {
        "action": change["action"],
        "classification": change["classification"],
        "evidence": change.get("evidence", {}),
        "kind": change["kind"],
        "location": change["location"],
        "location_kind": change["location_kind"],
        "message": change.get("message", ""),
        "rule_id": change["rule_id"],
    }
    if "policy_severity" in change:
        body["policy_severity"] = change["policy_severity"]
    return _digest(body)


def _change_sort_key(change: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(change.get("location", "")),
        str(change.get("rule_id", "")),
        str(change.get("classification", "")),
        str(change.get("kind", "")),
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
