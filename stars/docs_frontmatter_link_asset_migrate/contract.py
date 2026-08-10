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

STAR_NAME: Final = "orrery/docs-frontmatter-link-asset-migrate"
STAR_VERSION: Final = "0.1.0"
MAX_ENTRIES: Final = 256
MAX_ENTRY_BYTES: Final = 256 * 1024
MAX_FINDINGS: Final = 4096
MAX_MESSAGE_BYTES: Final = 512
MAX_PATCH_BYTES: Final = 256 * 1024
MAX_PATH_LEN: Final = 512
MAX_RULE_MAP_ENTRIES: Final = 512

FEATURE_CLASSES: Final = frozenset(
    {"safe", "transformable", "decision_required", "unsupported", "malformed"}
)

DEFAULT_SUPPORTED_ASSET_EXTENSIONS: Final = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".webp",
    ".pdf",
)

EXECUTION_GRANTS: Final = frozenset({"fetch_remote_urls", "copy_external_assets"})

TOOL_SCHEMAS: Final = {
    "migrate": {
        "description": (
            "Apply profile rules to migrate frontmatter fields, internal "
            "document links, anchors, and asset references. Returns a "
            "bounded patch plus a before/after link/asset report without "
            "fetching remote URLs or copying external assets unless "
            "explicitly granted."
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
                },
                "rules": {
                    "type": "object",
                    "properties": {
                        "field_renames": {
                            "type": "object",
                            "additionalProperties": {"type": "string"},
                        },
                        "path_redirects": {
                            "type": "object",
                            "additionalProperties": {"type": "string"},
                        },
                        "anchor_redirects": {
                            "type": "object",
                            "additionalProperties": {"type": "string"},
                        },
                        "supported_asset_extensions": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "execution_grants": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": sorted(EXECUTION_GRANTS),
                            },
                        },
                    },
                    "additionalProperties": False,
                },
            },
            "required": ["entries"],
            "additionalProperties": False,
        },
    }
}


def tool_schemas() -> dict[str, object]:
    return copy.deepcopy(TOOL_SCHEMAS)
