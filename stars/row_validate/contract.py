from __future__ import annotations

from typing import Final

STAR_NAME: Final = "orrery/row-validate"
STAR_VERSION: Final = "0.1.0"
DEFAULT_PROFILE: Final = "flights-airport"
MAX_ERRORS: Final = 10
PROFILES: Final = {
    DEFAULT_PROFILE: {
        "version": "1",
        "fields": {
            "origin": {"type": "string", "pattern": "^[A-Z]{3}$", "maxLength": 3},
            "destination": {"type": "string", "pattern": "^[A-Z]{3}$", "maxLength": 3},
            "count": {"type": "integer", "minimum": 0},
        },
    }
}
ROW_SCHEMA: Final = {
    "type": "object",
    "properties": PROFILES[DEFAULT_PROFILE]["fields"],
    "required": ["origin", "destination", "count"],
    "additionalProperties": False,
}
TOOL_SCHEMAS: Final = {
    "validate": {
        "description": "Validate one small row against a named static source-aligned profile.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "profile": {
                    "type": "string",
                    "enum": [DEFAULT_PROFILE],
                    "default": DEFAULT_PROFILE,
                },
                "row": ROW_SCHEMA,
            },
            "required": ["profile", "row"],
            "additionalProperties": False,
        },
    }
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
