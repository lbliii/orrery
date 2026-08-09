from __future__ import annotations

from typing import Final

STAR_NAME: Final = "orrery/csv-url"
STAR_VERSION: Final = "0.1.0"
DEFAULT_DATASET: Final = "cars"
DATASET_URLS: Final = {
    "airports": "https://raw.githubusercontent.com/vega/vega-datasets/main/data/airports.csv",
    "cars": "https://raw.githubusercontent.com/vega/vega-datasets/main/data/cars.csv",
    "seattle-weather": (
        "https://raw.githubusercontent.com/vega/vega-datasets/main/data/seattle-weather.csv"
    ),
}
MAX_BYTES: Final = 512 * 1024
MAX_ROWS: Final = 100

TOOL_SCHEMAS: Final = {
    "get": {
        "description": "Get typed, bounded rows from a named allowlisted public CSV dataset.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dataset": {
                    "type": "string",
                    "enum": sorted(DATASET_URLS),
                    "default": DEFAULT_DATASET,
                },
            },
            "required": ["dataset"],
        },
    }
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
