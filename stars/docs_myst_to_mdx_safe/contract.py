from __future__ import annotations

from typing import Final, Literal

FeatureClass = Literal[
    "safe",
    "transformable",
    "decision_required",
    "unsupported",
    "malformed",
]

STAR_NAME: Final = "orrery/docs-myst-to-mdx-safe"
STAR_VERSION: Final = "0.1.0"
MAX_ENTRIES: Final = 256
MAX_ENTRY_BYTES: Final = 256 * 1024
MAX_FINDINGS: Final = 4096
MAX_MESSAGE_BYTES: Final = 512

FEATURE_CLASSES: Final = frozenset(
    {"safe", "transformable", "decision_required", "unsupported", "malformed"}
)

# Corpus-backed subset for docs/myst-to-mdx-baseline (ADR 0008 §13 A / fixture profile).
CORPUS_SAFE_FEATURES: Final = frozenset({"md.heading"})
CORPUS_TRANSFORMABLE_FEATURES: Final = frozenset({"myst.directive.admonition"})
CORPUS_FEATURES: Final = CORPUS_SAFE_FEATURES | CORPUS_TRANSFORMABLE_FEATURES

HOLD_CLASSES: Final = frozenset({"decision_required", "unsupported", "malformed"})

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
            "Plan a safe MyST→MDX baseline transform from caller-held entries "
            "and a pinned MigrationProfile. Unsupported constructs become "
            "findings/hold ops — never silent plain-text drops."
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
            "Apply a sealed plan to caller-held entries and return an ADR 0008 "
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
