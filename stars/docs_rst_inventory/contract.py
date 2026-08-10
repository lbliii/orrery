from __future__ import annotations

from typing import Final, Literal

FeatureClass = Literal[
    "safe",
    "transformable",
    "decision_required",
    "unsupported",
    "malformed",
]

STAR_NAME: Final = "orrery/docs-rst-inventory"
STAR_VERSION: Final = "0.1.0"
MAX_ENTRIES: Final = 256
MAX_ENTRY_BYTES: Final = 256 * 1024
MAX_FINDINGS: Final = 4096
MAX_MESSAGE_BYTES: Final = 512

FEATURE_CLASSES: Final = frozenset(
    {"safe", "transformable", "decision_required", "unsupported", "malformed"}
)

ADMONITION_DIRECTIVES: Final = frozenset(
    {
        "admonition",
        "attention",
        "caution",
        "danger",
        "error",
        "hint",
        "important",
        "note",
        "tip",
        "warning",
    }
)

AUTODOC_DIRECTIVES: Final = frozenset(
    {
        "automodule",
        "autoclass",
        "autofunction",
        "autodata",
        "automethod",
        "autoattribute",
        "autoproperty",
        "autoexception",
        "autosummary",
    }
)

TABLE_DIRECTIVES: Final = frozenset(
    {"table", "list-table", "csv-table", "flat-table"}
)

SAFE_DIRECTIVES: Final = frozenset(
    {"code-block", "code", "highlight", "image", "figure", "literal"}
)

TRANSFORMABLE_ROLES: Final = frozenset({"ref", "doc", "term", "abbr", "title"})

TOOL_SCHEMAS: Final = {
    "inventory": {
        "description": (
            "Parse a bounded reStructuredText/Sphinx documentation tree and emit "
            "a deterministic inventory with classified findings and stable digests."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "entries": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": MAX_ENTRIES,
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "minLength": 1},
                            "content": {"type": "string"},
                        },
                        "required": ["path", "content"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["entries"],
            "additionalProperties": False,
        },
    }
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
