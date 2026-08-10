from __future__ import annotations

from typing import Final, Literal

ChangeClassification = Literal[
    "breaking",
    "behavioral",
    "additive",
    "informational",
    "unknown",
    "policy-exempt",
]

PolicyAction = Literal["allow", "report", "block", "decision_required"]
PolicySeverity = Literal["breaking", "behavioral", "informational"]

STAR_NAME: Final = "orrery/api-spec-compatibility-diff"
STAR_VERSION: Final = "0.1.0"
MAX_ENTRIES: Final = 256
MAX_ENTRY_BYTES: Final = 256 * 1024
MAX_CHANGES: Final = 4096
MAX_MESSAGE_BYTES: Final = 512

CHANGE_CLASSIFICATIONS: Final = frozenset(
    {
        "breaking",
        "behavioral",
        "additive",
        "informational",
        "unknown",
        "policy-exempt",
    }
)

POLICY_ACTIONS: Final = frozenset({"allow", "report", "block", "decision_required"})
POLICY_SEVERITIES: Final = frozenset({"breaking", "behavioral", "informational"})

# Detected change kinds mapped to ADR 0008 compatibility_policy.rules[].id values
# (and additive/unknown kinds that extend classification beyond rule severity).
RULE_PATH_REMOVE: Final = "breaking.path.remove"
RULE_SCHEMA_REMOVE: Final = "breaking.schema.remove"
RULE_INFO_DESCRIPTION: Final = "info.description.change"
RULE_PATH_ADD: Final = "additive.path.add"
RULE_SCHEMA_ADD: Final = "additive.schema.add"
RULE_SCHEMA_CHANGE: Final = "unknown.schema.change"
RULE_OPERATION_CHANGE: Final = "unknown.operation.change"

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

COMPATIBILITY_POLICY_SCHEMA: Final = {
    "type": "object",
    "properties": {
        "policy_id": {"type": "string", "minLength": 1},
        "default_action": {
            "type": "string",
            "enum": sorted(POLICY_ACTIONS),
        },
        "rules": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "severity": {
                        "type": "string",
                        "enum": sorted(POLICY_SEVERITIES),
                    },
                    "action": {
                        "type": "string",
                        "enum": sorted(POLICY_ACTIONS),
                    },
                },
                "required": ["id", "severity", "action"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["policy_id", "default_action", "rules"],
    "additionalProperties": False,
}

TOOL_SCHEMAS: Final = {
    "diff": {
        "description": (
            "Compare source and candidate target OpenAPI entries under an ADR 0008 "
            "compatibility_policy. Classify structural changes; never claim that "
            "structural equality implies runtime compatibility."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_entries": ENTRIES_SCHEMA,
                "target_entries": ENTRIES_SCHEMA,
                "compatibility_policy": COMPATIBILITY_POLICY_SCHEMA,
            },
            "required": ["source_entries", "target_entries", "compatibility_policy"],
            "additionalProperties": False,
        },
    }
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
