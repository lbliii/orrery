from __future__ import annotations

import copy
import hashlib
from collections.abc import Mapping
from typing import Any, Final, Literal

FeatureClass = Literal[
    "safe",
    "transformable",
    "decision_required",
    "unsupported",
    "malformed",
]

STAR_NAME: Final = "orrery/api-spec-openapi-validate"
STAR_VERSION: Final = "0.1.0"
VALIDATOR_NAME: Final = "orrery/openapi-validate"
VALIDATOR_VERSION: Final = "1.0.0"

MAX_ENTRIES: Final = 256
MAX_ENTRY_BYTES: Final = 256 * 1024
MAX_FINDINGS: Final = 4096
MAX_MESSAGE_BYTES: Final = 512
MAX_PATH_LEN: Final = 512

FEATURE_CLASSES: Final = frozenset(
    {"safe", "transformable", "decision_required", "unsupported", "malformed"}
)

ENTRY_SCHEMA: Final = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "minLength": 1},
        "content": {"type": "string"},
    },
    "required": ["path", "content"],
    "additionalProperties": False,
}

ENTRIES_SCHEMA: Final = {
    "type": "array",
    "minItems": 1,
    "maxItems": MAX_ENTRIES,
    "items": ENTRY_SCHEMA,
}

TOOL_SCHEMAS: Final = {
    "validate": {
        "description": (
            "Run the pinned OpenAPI 3.1 parser/schema adapter against caller-held "
            "target bytes and optional sealed change_bundle. Emit ADR 0008 "
            "validation stage output with bounded diagnostics; schema conformance "
            "only — compatibility conclusions stay with compatibility-diff."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "target_entries": ENTRIES_SCHEMA,
                "change_bundle": {"type": "object"},
                "profile": {"type": "object"},
                "source_entries": ENTRIES_SCHEMA,
                "plan": {"type": "object"},
            },
            "required": ["target_entries", "change_bundle", "profile"],
            "additionalProperties": False,
        },
    }
}


def tool_schemas() -> dict[str, object]:
    return copy.deepcopy(TOOL_SCHEMAS)


def feature_finding_digest(finding: Mapping[str, Any]) -> str:
    """Digest for inventory-style validation findings (feature_id + class + path)."""
    body: dict[str, Any] = {
        "feature_id": finding["feature_id"],
        "class": finding["class"],
        "path": finding["path"],
    }
    message = finding.get("message")
    if isinstance(message, str) and message:
        body["message"] = message
    return _sha256_json(body)


def policy_finding_digest(rule_id: str) -> str:
    """Digest for compatibility-policy blocking findings (golden corpus contract)."""
    return hashlib.sha256(rule_id.encode("utf-8")).hexdigest()


def _sha256_json(value: Mapping[str, Any]) -> str:
    from stars._core.migration_profile import canonical_json, sha256_hex

    return sha256_hex(canonical_json(dict(value)))
