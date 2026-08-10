from __future__ import annotations

from typing import Final

STAR_NAME: Final = "orrery/link-check-bounded"
STAR_VERSION: Final = "0.1.0"
MAX_FILES: Final = 200
MAX_PATH_LEN: Final = 512
MAX_CONTENT_BYTES: Final = 256_000
MAX_LINK_COUNT_CAP: Final = 50
DEFAULT_MAX_LINK_COUNT: Final = 20
TIMEOUT_SECONDS: Final = 8

# Fixed HTTPS origins — hybrid star; not a general web fetcher.
ALLOWED_ORIGINS: Final = (
    "https://example.com",
    "https://docs.python.org",
)

FILE_ENTRY_SCHEMA: Final = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "minLength": 1, "maxLength": MAX_PATH_LEN},
        "content": {"type": "string"},
        "format": {"type": "string", "enum": ["markdown", "html"]},
    },
    "required": ["path", "content"],
    "additionalProperties": False,
}

TOOL_SCHEMAS: Final = {
    "check": {
        "description": (
            "Check links in a markdown/html bundle with an explicit max_link_count "
            "and allowlisted egress."
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
                "max_link_count": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": MAX_LINK_COUNT_CAP,
                    "default": DEFAULT_MAX_LINK_COUNT,
                },
            },
            "required": ["files", "max_link_count"],
            "additionalProperties": False,
        },
    }
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
