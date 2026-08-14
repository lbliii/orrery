from __future__ import annotations

from typing import Final

STAR_NAME: Final = "orrery/kida-check"
STAR_VERSION: Final = "0.1.0"
MAX_TEMPLATES: Final = 500
MAX_PATH_LEN: Final = 512
MAX_CONTENT_BYTES: Final = 256_000
MAX_FINDINGS: Final = 500
ALLOWED_SUFFIXES: Final = (".html", ".kida")

TEMPLATE_ENTRY_SCHEMA: Final = {
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
            "Statically validate caller-supplied Kida templates and return coded findings."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "templates": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": MAX_TEMPLATES,
                    "items": TEMPLATE_ENTRY_SCHEMA,
                },
                "validate_calls": {
                    "type": "boolean",
                    "description": "Validate component call sites against {% def %} signatures.",
                },
                "strict": {
                    "type": "boolean",
                    "description": "Fail on unified {% end %} closers instead of explicit tags.",
                },
            },
            "required": ["templates"],
            "additionalProperties": False,
        },
    }
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
