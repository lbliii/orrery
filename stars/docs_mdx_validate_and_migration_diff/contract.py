from __future__ import annotations

import copy
from typing import Final, Literal

FeatureClass = Literal[
    "safe",
    "transformable",
    "decision_required",
    "unsupported",
    "malformed",
]

STAR_NAME: Final = "orrery/docs-mdx-validate-and-migration-diff"
STAR_VERSION: Final = "0.1.0"
VALIDATOR_NAME: Final = "orrery/docs-mdx-validate"
VALIDATOR_VERSION: Final = "1.0.0"

MAX_ENTRIES: Final = 256
MAX_ENTRY_BYTES: Final = 256 * 1024
MAX_FINDINGS: Final = 4096
MAX_MESSAGE_BYTES: Final = 512
MAX_DIFF_ROWS: Final = 1024
MAX_PATH_LEN: Final = 512

FEATURE_CLASSES: Final = frozenset(
    {"safe", "transformable", "decision_required", "unsupported", "malformed"}
)

# Source feature → expected target feature after a successful safe transform.
SEMANTIC_EQUIVALENTS: Final = {
    "md.heading": frozenset({"md.heading"}),
    "myst.directive.admonition": frozenset(
        {"mdx.component.admonition", "myst.directive.admonition"}
    ),
}

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
            "Run the pinned MDX validator/build adapter and compare source "
            "inventory to target inventory. Emit a sealed validation stage "
            "plus bounded migration-diff evidence (build status, unresolved "
            "links/assets, dropped/added constructs, mapping coverage). "
            "Does not claim runtime compatibility."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_entries": ENTRIES_SCHEMA,
                "target_entries": ENTRIES_SCHEMA,
                "change_bundle": {"type": "object"},
                "profile": {"type": "object"},
                "plan": {"type": "object"},
                "link_asset_report": {"type": "object"},
            },
            "required": [
                "source_entries",
                "target_entries",
                "change_bundle",
                "profile",
            ],
            "additionalProperties": False,
        },
    }
}


def tool_schemas() -> dict[str, object]:
    return copy.deepcopy(TOOL_SCHEMAS)
