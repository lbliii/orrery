"""MigrationProfile v1 validation and digest helpers (ADR 0008)."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any

PROFILE_SCHEMA_VERSION = "migration-profile/v1"

REQUIRED_ROOT_FIELDS: frozenset[str] = frozenset(
    {
        "schema_version",
        "profile_id",
        "version",
        "source",
        "target",
        "feature_vocabulary",
        "compatibility_policy",
        "execution_locality",
        "transformer",
        "validator",
        "retention_redaction",
        "profile_digest",
    }
)
OPTIONAL_ROOT_FIELDS: frozenset[str] = frozenset({"title", "description", "supersedes"})
ALLOWED_ROOT_FIELDS = REQUIRED_ROOT_FIELDS | OPTIONAL_ROOT_FIELDS

EXECUTION_LOCALITIES: frozenset[str] = frozenset(
    {"agent_local", "creator_owned_tooling", "orrery_coord_only"}
)
FEATURE_CLASSES: frozenset[str] = frozenset(
    {"safe", "transformable", "decision_required", "unsupported", "malformed"}
)
POLICY_ACTIONS: frozenset[str] = frozenset({"allow", "report", "block", "decision_required"})
POLICY_SEVERITIES: frozenset[str] = frozenset({"breaking", "behavioral", "informational"})

_FLOATING_PIN = re.compile(r"(^|\s)(latest|\*|\^|~|>=)")
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


class MigrationProfileError(ValueError):
    """A MigrationProfile document violates ADR 0008."""


def canonical_json(obj: Any) -> bytes:
    """Canonical UTF-8 JSON per ADR 0008 / envelope-verification."""
    normalized = _nfc_wire(obj)
    return json.dumps(
        normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compute_profile_digest(profile: Mapping[str, Any]) -> str:
    without = {key: value for key, value in profile.items() if key != "profile_digest"}
    return sha256_hex(canonical_json(without))


def validate_version_pin(version: object) -> str | None:
    if not isinstance(version, str) or not version.strip():
        return "version_pin_empty"
    if _FLOATING_PIN.search(version):
        return "version_pin_floating"
    return None


def validate_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    """Validate profile shape and digest; return loud error dict or normalized profile."""
    if not isinstance(profile, Mapping):
        return {"error": "profile_not_object"}

    extra = set(profile) - ALLOWED_ROOT_FIELDS
    if extra:
        return {"error": "profile_forbidden_root_keys", "keys": sorted(extra)}

    missing = REQUIRED_ROOT_FIELDS - set(profile)
    if missing:
        return {"error": "profile_missing_fields", "fields": sorted(missing)}

    if profile["schema_version"] != PROFILE_SCHEMA_VERSION:
        return {
            "error": "profile_schema_version",
            "expected": PROFILE_SCHEMA_VERSION,
            "actual": profile["schema_version"],
        }

    for field in ("profile_id", "version"):
        if not isinstance(profile[field], str) or not profile[field].strip():
            return {"error": "profile_invalid_string", "field": field}

    for pin_field in ("source", "target"):
        pin_error = _validate_kind_version(profile[pin_field], field=pin_field)
        if pin_error is not None:
            return pin_error

    vocab_error = _validate_feature_vocabulary(profile["feature_vocabulary"])
    if vocab_error is not None:
        return vocab_error

    policy_error = _validate_compatibility_policy(profile["compatibility_policy"])
    if policy_error is not None:
        return policy_error

    if profile["execution_locality"] not in EXECUTION_LOCALITIES:
        return {
            "error": "execution_locality_invalid",
            "value": profile["execution_locality"],
        }

    for tool_field in ("transformer", "validator"):
        tool_error = _validate_tool_identity(profile[tool_field], field=tool_field)
        if tool_error is not None:
            return tool_error

    retention_error = _validate_retention_redaction(profile["retention_redaction"])
    if retention_error is not None:
        return retention_error

    if not isinstance(profile["profile_digest"], str) or not _SHA256_HEX.fullmatch(
        profile["profile_digest"]
    ):
        return {"error": "profile_digest_invalid"}

    expected = compute_profile_digest(profile)
    if profile["profile_digest"] != expected:
        return {
            "error": "profile_digest_mismatch",
            "expected": expected,
            "actual": profile["profile_digest"],
        }

    return {"valid": True, "profile": dict(profile), "profile_digest": expected}


def require_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    """Validate profile or raise :class:`MigrationProfileError`."""
    result = validate_profile(profile)
    if result.get("valid"):
        return result["profile"]
    raise MigrationProfileError(json.dumps(result, sort_keys=True))


def resolve_floating_request(
    request: Mapping[str, Any],
    catalog: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Resolve a floating migration request to a pinned profile reference."""
    family = request.get("family")
    if not isinstance(family, str) or not family.strip():
        return {"error": "family_required"}
    if request.get("target") in {"latest", "*"}:
        return {
            "error": "floating_target_rejected",
            "resolution_reason": "floating_target_rejected",
        }

    constraints = request.get("constraints") or {}
    if not isinstance(constraints, Mapping):
        return {"error": "constraints_invalid"}

    max_major = constraints.get("max_profile_major")
    policy_id = request.get("policy_id")
    source_hint = request.get("source_hint")

    candidates: list[Mapping[str, Any]] = []
    for entry in catalog:
        validated = validate_profile(entry)
        if not validated.get("valid"):
            continue
        pinned = validated["profile"]
        if not str(pinned["profile_id"]).startswith(family):
            continue
        if policy_id is not None and pinned["compatibility_policy"]["policy_id"] != policy_id:
            continue
        if isinstance(source_hint, Mapping):
            source = pinned["source"]
            if source_hint.get("kind") and source_hint["kind"] != source["kind"]:
                continue
            if source_hint.get("version") and source_hint["version"] != source["version"]:
                continue
        candidates.append(pinned)

    if not candidates:
        return {"error": "no_unique_profile", "resolution_reason": "no_unique_profile"}

    def sort_key(item: Mapping[str, Any]) -> tuple[int, ...]:
        parts = str(item["version"]).split(".")
        nums = tuple(int(part) for part in parts[:3]) if len(parts) >= 3 else (0, 0, 0)
        if isinstance(max_major, int) and nums[0] > max_major:
            return (-1, -1, -1)
        return nums

    ranked = [item for item in candidates if sort_key(item)[0] >= 0]
    if not ranked:
        return {"error": "no_unique_profile", "resolution_reason": "no_unique_profile"}
    ranked.sort(key=sort_key, reverse=True)
    top = sort_key(ranked[0])
    if len([item for item in ranked if sort_key(item) == top]) > 1:
        return {"error": "no_unique_profile", "resolution_reason": "no_unique_profile"}

    chosen = ranked[0]
    return {
        "profile_id": chosen["profile_id"],
        "version": chosen["version"],
        "profile_digest": chosen["profile_digest"],
        "resolution_reason": "catalog_match",
    }


def _validate_kind_version(value: object, *, field: str) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return {"error": "profile_invalid_object", "field": field}
    if set(value) != {"kind", "version"}:
        return {"error": "profile_invalid_pin_shape", "field": field}
    if not isinstance(value["kind"], str) or not value["kind"].strip():
        return {"error": "profile_invalid_string", "field": f"{field}.kind"}
    pin_error = validate_version_pin(value["version"])
    if pin_error is not None:
        return {"error": pin_error, "field": f"{field}.version"}
    return None


def _validate_feature_vocabulary(value: object) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return {"error": "profile_invalid_object", "field": "feature_vocabulary"}
    if set(value) != {"supported", "unsupported"}:
        return {"error": "profile_invalid_vocabulary_shape"}
    for bucket in ("supported", "unsupported"):
        entries = value[bucket]
        if not isinstance(entries, list):
            return {"error": "profile_invalid_list", "field": f"feature_vocabulary.{bucket}"}
        for index, entry in enumerate(entries):
            if not isinstance(entry, Mapping):
                return {
                    "error": "profile_invalid_object",
                    "field": f"feature_vocabulary.{bucket}[{index}]",
                }
            if set(entry) != {"id", "class"}:
                return {
                    "error": "profile_invalid_feature_entry",
                    "field": f"feature_vocabulary.{bucket}[{index}]",
                }
            if entry["class"] not in FEATURE_CLASSES:
                return {
                    "error": "profile_invalid_feature_class",
                    "field": f"feature_vocabulary.{bucket}[{index}].class",
                }
    return None


def _validate_compatibility_policy(value: object) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return {"error": "profile_invalid_object", "field": "compatibility_policy"}
    required = {"policy_id", "default_action", "rules"}
    if set(value) != required:
        return {"error": "profile_invalid_policy_shape"}
    if not isinstance(value["policy_id"], str) or not value["policy_id"].strip():
        return {"error": "profile_invalid_string", "field": "compatibility_policy.policy_id"}
    if value["default_action"] not in POLICY_ACTIONS:
        return {"error": "profile_invalid_policy_action", "field": "default_action"}
    if not isinstance(value["rules"], list):
        return {"error": "profile_invalid_list", "field": "compatibility_policy.rules"}
    for index, rule in enumerate(value["rules"]):
        if not isinstance(rule, Mapping):
            return {
                "error": "profile_invalid_object",
                "field": f"compatibility_policy.rules[{index}]",
            }
        if set(rule) != {"id", "severity", "action"}:
            return {"error": "profile_invalid_rule_shape", "field": f"rules[{index}]"}
        if rule["severity"] not in POLICY_SEVERITIES:
            return {"error": "profile_invalid_severity", "field": f"rules[{index}].severity"}
        if rule["action"] not in POLICY_ACTIONS:
            return {"error": "profile_invalid_policy_action", "field": f"rules[{index}].action"}
    return None


def _validate_tool_identity(value: object, *, field: str) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return {"error": "profile_invalid_object", "field": field}
    if set(value) != {"name", "version", "digest"}:
        return {"error": "profile_invalid_tool_shape", "field": field}
    for sub in ("name", "version", "digest"):
        if not isinstance(value[sub], str) or not value[sub].strip():
            return {"error": "profile_invalid_string", "field": f"{field}.{sub}"}
    pin_error = validate_version_pin(value["version"])
    if pin_error is not None:
        return {"error": pin_error, "field": f"{field}.version"}
    if not _SHA256_HEX.fullmatch(value["digest"]):
        return {"error": "profile_invalid_tool_digest", "field": f"{field}.digest"}
    return None


def _validate_retention_redaction(value: object) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return {"error": "profile_invalid_object", "field": "retention_redaction"}
    required = {
        "receipt_includes",
        "receipt_excludes_by_default",
        "max_finding_message_bytes",
        "max_diagnostics_bytes",
    }
    if set(value) != required:
        return {"error": "profile_invalid_retention_shape"}
    for list_field in ("receipt_includes", "receipt_excludes_by_default"):
        items = value[list_field]
        if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
            return {"error": "profile_invalid_list", "field": f"retention_redaction.{list_field}"}
    for int_field in ("max_finding_message_bytes", "max_diagnostics_bytes"):
        if not isinstance(value[int_field], int) or value[int_field] < 0:
            return {"error": "profile_invalid_int", "field": f"retention_redaction.{int_field}"}
    return None


def _nfc_wire(value: Any) -> Any:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, Mapping):
        return {str(key): _nfc_wire(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_nfc_wire(item) for item in value]
    return value
