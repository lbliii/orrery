from __future__ import annotations

from typing import Final

STAR_NAME: Final = "orrery/manifest-preflight"
STAR_VERSION: Final = "0.1.0"
MAX_FILES: Final = 10_000
MAX_PATH_LEN: Final = 512
SHA256_HEX_LEN: Final = 64

POLICY_DOCS_ONLY: Final = "orrery/docs-only@v1"
POLICY_MAX_100: Final = "orrery/max-100-files@v1"
KNOWN_POLICIES: Final = frozenset({POLICY_DOCS_ONLY, POLICY_MAX_100})

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
    "check": {
        "description": (
            "Preflight a caller-supplied file manifest against a named versioned policy."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "files": {
                    "type": "array",
                    "maxItems": MAX_FILES,
                    "items": FILE_ENTRY_SCHEMA,
                },
                "policy": {
                    "type": "string",
                    "enum": sorted(KNOWN_POLICIES),
                },
                "manifest_digest": {
                    "type": "string",
                    "minLength": SHA256_HEX_LEN,
                    "maxLength": SHA256_HEX_LEN,
                },
            },
            "required": ["files", "policy"],
            "additionalProperties": False,
        },
    }
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
