"""Pure static validation of one bounded tax-jurisdiction record shape."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping

from .contract import DEFAULT_PROFILE, MAX_ERRORS, PROFILES


def validate(
    profile: str = DEFAULT_PROFILE, jurisdiction: object = None
) -> dict[str, object]:
    """Validate jurisdiction shape without remittance, filing, or payout logic."""
    definition = PROFILES.get(profile)
    if definition is None:
        return {"error": "profile_not_allowed", "profile": profile, "live_at_call": True}
    fields = definition["fields"]
    errors = _errors(jurisdiction, fields)
    result: dict[str, object] = {
        "profile": profile,
        "profile_version": definition["version"],
        "profile_digest": _digest(definition),
        "valid": not errors,
        "errors": errors[:MAX_ERRORS],
        "errors_truncated": len(errors) > MAX_ERRORS,
        "live_at_call": True,
    }
    if not errors:
        assert isinstance(jurisdiction, Mapping)
        result["normalized_jurisdiction"] = {
            field: jurisdiction[field] for field in fields
        }
    return result


def _errors(record: object, fields: Mapping[str, object]) -> list[dict[str, str]]:
    if not isinstance(record, Mapping):
        return [{"path": "$", "code": "type", "expected": "object"}]
    errors: list[dict[str, str]] = []
    for name, rule in fields.items():
        assert isinstance(rule, Mapping)
        if name not in record:
            errors.append({"path": f"$.{name}", "code": "required", "expected": "present"})
            continue
        value = record[name]
        if rule["type"] == "string":
            if not isinstance(value, str):
                errors.append({"path": f"$.{name}", "code": "type", "expected": "string"})
            elif not re.fullmatch(str(rule["pattern"]), value):
                errors.append(
                    {
                        "path": f"$.{name}",
                        "code": "pattern",
                        "expected": str(rule.get("description", "matching pattern")),
                    }
                )
        elif not isinstance(value, int) or isinstance(value, bool):
            errors.append({"path": f"$.{name}", "code": "type", "expected": "integer"})
        elif value < int(rule["minimum"]):
            errors.append({"path": f"$.{name}", "code": "minimum", "expected": "integer >= 0"})
    for name in sorted(set(record) - set(fields)):
        errors.append(
            {"path": f"$.{name}", "code": "additional_property", "expected": "no extra fields"}
        )
    return errors


def _digest(definition: Mapping[str, object]) -> str:
    canonical = json.dumps(definition, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"
