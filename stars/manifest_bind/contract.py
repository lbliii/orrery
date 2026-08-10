from __future__ import annotations

from typing import Final

STAR_NAME: Final = "orrery/manifest-bind"
STAR_VERSION: Final = "0.1.0"
MAX_FILES: Final = 10_000
MAX_PATH_LEN: Final = 512
SHA256_HEX_LEN: Final = 64

FILE_ENTRY_SCHEMA: Final = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "minLength": 1, "maxLength": MAX_PATH_LEN},
        "sha256": {"type": "string", "minLength": SHA256_HEX_LEN, "maxLength": SHA256_HEX_LEN},
        "size": {"type": "integer", "minimum": 0},
    },
    "required": ["path", "sha256", "size"],
    "additionalProperties": False,
}

TOOL_SCHEMAS: Final = {
    "bind": {
        "description": (
            "Bind a caller-supplied file list into a stable manifest_digest with "
            "admitted and excluded counts."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "files": {
                    "type": "array",
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
