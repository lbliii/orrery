from __future__ import annotations

from typing import Final

STAR_NAME: Final = "orrery/structure-audit"
STAR_VERSION: Final = "0.1.0"
MAX_FILES: Final = 500
MAX_PATH_LEN: Final = 512
MAX_CONTENT_BYTES: Final = 256_000
MAX_FINDINGS: Final = 500

FILE_ENTRY_SCHEMA: Final = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "minLength": 1, "maxLength": MAX_PATH_LEN},
        "content": {"type": "string"},
    },
    "required": ["path", "content"],
    "additionalProperties": False,
}

TOOL_SCHEMAS: Final = {
    "audit": {
        "description": (
            "Audit a markdown file set for heading gaps, frontmatter errors, and orphans."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "files": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": MAX_FILES,
                    "items": FILE_ENTRY_SCHEMA,
                },
            },
            "required": ["files"],
            "additionalProperties": False,
        },
    }
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
