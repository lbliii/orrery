from __future__ import annotations

from typing import Final

STAR_NAME: Final = "orrery/kida-render"
STAR_VERSION: Final = "0.1.0"
MAX_TEMPLATE_BYTES: Final = 256_000
MAX_DATA_JSON_BYTES: Final = 256_000
MAX_OUTPUT_BYTES: Final = 256_000
MAX_PATH_LEN: Final = 512
WALL_TIMEOUT_SECONDS: Final = 30.0
ALLOWED_SURFACES: Final = ("html",)
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
    "render": {
        "description": (
            "Render caller-supplied Kida template bytes with JSON data to an HTML "
            "surface and return stable digests — sync, in-memory, no egress."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "template": {
                    "oneOf": [
                        {"type": "string", "minLength": 1},
                        TEMPLATE_ENTRY_SCHEMA,
                        {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 1,
                            "items": TEMPLATE_ENTRY_SCHEMA,
                        },
                    ],
                },
                "data": {"type": "object"},
                "surface": {
                    "type": "string",
                    "enum": list(ALLOWED_SURFACES),
                    "default": "html",
                },
            },
            "required": ["template", "data"],
            "additionalProperties": False,
        },
    }
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
