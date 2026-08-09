from __future__ import annotations

from typing import Final

STAR_NAME: Final = "orrery/table-diff"
STAR_VERSION: Final = "0.1.0"
MAX_ROWS: Final = 100
MAX_COLUMNS: Final = 25
MAX_INPUT_BYTES: Final = 64 * 1024
MAX_STRING_CHARS: Final = 1_024
MAX_EXAMPLES: Final = 20

SCALAR_SCHEMA: Final = {
    "anyOf": [
        {"type": "string", "maxLength": MAX_STRING_CHARS},
        {"type": "integer"},
        {"type": "number"},
        {"type": "boolean"},
        {"type": "null"},
    ]
}
ROW_SCHEMA: Final = {
    "type": "object",
    "minProperties": 1,
    "maxProperties": MAX_COLUMNS,
    "additionalProperties": SCALAR_SCHEMA,
}
SNAPSHOT_SCHEMA: Final = {
    "type": "object",
    "properties": {
        "rows": {"type": "array", "maxItems": MAX_ROWS, "items": ROW_SCHEMA},
        "digest": {"type": "string", "maxLength": 200},
    },
    "required": ["rows"],
    "additionalProperties": False,
}

TOOL_SCHEMAS: Final = {
    "diff": {
        "description": "Compare two small table snapshots using one explicit unique key column.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "left": SNAPSHOT_SCHEMA,
                "right": SNAPSHOT_SCHEMA,
                "key_column": {"type": "string", "minLength": 1, "maxLength": 128},
            },
            "required": ["left", "right", "key_column"],
            "additionalProperties": False,
        },
    }
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
