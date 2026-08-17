from __future__ import annotations

from typing import Final

STAR_NAME: Final = "orrery/plugin-preflight"
STAR_VERSION: Final = "0.1.0"
MAX_FILES: Final = 500
MAX_PATH_LEN: Final = 512
MAX_CONTENT_BYTES: Final = 256_000
SHA256_HEX_LEN: Final = 64

PROFILE_V1: Final = "agent-plugins/1.0.0"
KNOWN_PROFILES: Final = frozenset({PROFILE_V1})

PLUGIN_SCHEMA_ID: Final = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
MCP_SCHEMA_ID: Final = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"

PLUGIN_TOP_LEVEL: Final = frozenset(
    {
        "$schema",
        "name",
        "version",
        "description",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
        "extensions",
    }
)
AUTHOR_FIELDS: Final = frozenset({"name", "email", "url"})
FATAL_CODES: Final = frozenset(
    {
        "plugin_json_missing",
        "plugin_json_invalid",
        "name_invalid",
        "schema_unsupported",
        "path_escape",
    }
)
ADVISORY_CODES: Final = frozenset({"secret_like_header", "secret_like_env"})

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
    "check": {
        "description": (
            "Preflight a caller-supplied plugin bundle against Agent Plugins 1.0.0."
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
                "profile": {
                    "type": "string",
                    "enum": sorted(KNOWN_PROFILES),
                    "default": PROFILE_V1,
                },
                "manifest_digest": {
                    "type": "string",
                    "minLength": SHA256_HEX_LEN,
                    "maxLength": SHA256_HEX_LEN,
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
