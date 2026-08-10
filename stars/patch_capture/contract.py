from __future__ import annotations

from typing import Final

STAR_NAME: Final = "orrery/patch-capture"
STAR_VERSION: Final = "0.1.0"
MAX_FILES: Final = 10_000
MAX_PATH_LEN: Final = 512
SHA256_HEX_LEN: Final = 64
MAX_CONTENT_BYTES: Final = 256 * 1024

FILE_ENTRY_SCHEMA: Final = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "minLength": 1, "maxLength": MAX_PATH_LEN},
        "sha256": {"type": "string", "minLength": SHA256_HEX_LEN, "maxLength": SHA256_HEX_LEN},
        "size": {"type": "integer", "minimum": 0},
        "content": {"type": "string", "maxLength": MAX_CONTENT_BYTES},
    },
    "required": ["path", "sha256", "size"],
    "additionalProperties": False,
}

SNAPSHOT_SCHEMA: Final = {
    "type": "object",
    "properties": {
        "files": {
            "type": "array",
            "maxItems": MAX_FILES,
            "items": FILE_ENTRY_SCHEMA,
        }
    },
    "required": ["files"],
    "additionalProperties": False,
}

TOOL_SCHEMAS: Final = {
    "capture": {
        "description": (
            "Capture a patch receipt from before/after file snapshots or "
            "manifest pairs; returns patch_digest, changed paths, and line stats."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "before": SNAPSHOT_SCHEMA,
                "after": SNAPSHOT_SCHEMA,
            },
            "required": ["before", "after"],
            "additionalProperties": False,
        },
    }
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
