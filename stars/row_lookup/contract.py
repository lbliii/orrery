from __future__ import annotations

from typing import Final

STAR_NAME: Final = "orrery/row-lookup"
STAR_VERSION: Final = "0.1.0"
DEFAULT_DATASET: Final = "flights-airport"
FLIGHTS_AIRPORT_URL: Final = (
    "https://raw.githubusercontent.com/vega/vega-datasets/main/data/flights-airport.csv"
)
DATASET_URLS: Final = {DEFAULT_DATASET: FLIGHTS_AIRPORT_URL}
MAX_BYTES: Final = 512 * 1024
MAX_ROWS_SCANNED: Final = 10_000

KEY_SCHEMA: Final = {
    "origin": {"type": "string", "pattern": "^[A-Z]{3}$"},
    "destination": {"type": "string", "pattern": "^[A-Z]{3}$"},
}
TOOL_SCHEMAS: Final = {
    "lookup": {
        "description": "Look up one exact flight aggregate from an allowlisted dataset.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dataset": {
                    "type": "string",
                    "enum": [DEFAULT_DATASET],
                    "default": DEFAULT_DATASET,
                },
                "key": {
                    "type": "object",
                    "properties": KEY_SCHEMA,
                    "required": ["origin", "destination"],
                    "additionalProperties": False,
                },
            },
            "required": ["dataset", "key"],
            "additionalProperties": False,
        },
    }
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
