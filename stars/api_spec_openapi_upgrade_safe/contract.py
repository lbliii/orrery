from __future__ import annotations

from typing import Final, Literal

FeatureClass = Literal[
    "safe",
    "transformable",
    "decision_required",
    "unsupported",
    "malformed",
]

STAR_NAME: Final = "orrery/api-spec-openapi-upgrade-safe"
STAR_VERSION: Final = "0.1.0"
MAX_ENTRIES: Final = 256
MAX_ENTRY_BYTES: Final = 256 * 1024
MAX_FINDINGS: Final = 4096
MAX_MESSAGE_BYTES: Final = 512

FEATURE_CLASSES: Final = frozenset(
    {"safe", "transformable", "decision_required", "unsupported", "malformed"}
)

# Corpus-backed subset for api-spec/openapi-3-0-to-3-1-safe (ADR 0008 fixture).
CORPUS_SAFE_FEATURES: Final = frozenset(
    {
        "openapi.version",
        "openapi.operation",
        "openapi.schema",
        "openapi.security_scheme",
        "openapi.format",
        "openapi.example",
        "openapi.examples",
        "openapi.ref.internal",
        "openapi.ref.document",
    }
)
CORPUS_TRANSFORMABLE_FEATURES: Final = frozenset(
    {
        "openapi.json_schema.draft2020",
        "openapi.nullable",
    }
)
CORPUS_FEATURES: Final = CORPUS_SAFE_FEATURES | CORPUS_TRANSFORMABLE_FEATURES

HOLD_CLASSES: Final = frozenset({"decision_required", "unsupported", "malformed"})

PINNED_PROFILE_ID: Final = "api-spec/openapi-3-0-to-3-1-safe"
PINNED_SOURCE: Final = {"kind": "openapi", "version": "3.0.3"}
PINNED_TARGET: Final = {"kind": "openapi", "version": "3.1.0"}

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
    "plan": {
        "description": (
            "Plan a pinned OpenAPI 3.0.3→3.1.0 safe upgrade from caller-held "
            "entries and a MigrationProfile. Unsupported / decision-required "
            "constructs become findings and hold ops — never a floating latest."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "entries": ENTRIES_SCHEMA,
                "profile": {"type": "object"},
            },
            "required": ["entries", "profile"],
            "additionalProperties": False,
        },
    },
    "apply": {
        "description": (
            "Apply a sealed OpenAPI upgrade plan and return an ADR 0008 "
            "change_bundle plus target file bytes. Does not mutate a checkout. "
            "Rejects plans sealed for a different source or profile digest."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "entries": ENTRIES_SCHEMA,
                "plan": {"type": "object"},
                "profile": {"type": "object"},
            },
            "required": ["entries", "plan", "profile"],
            "additionalProperties": False,
        },
    },
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
