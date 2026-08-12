from __future__ import annotations

from typing import Final

STAR_NAME: Final = "orrery/table-fresh"
STAR_VERSION: Final = "0.1.0"
CURRENT_DATASET: Final = "flights-airport"
MAX_ROWS: Final = 100

BASELINE_ROW_SCHEMA: Final = {
    "type": "object",
    "properties": {
        "origin": {"type": "string", "pattern": "^[A-Z]{3}$", "maxLength": 3},
        "destination": {"type": "string", "pattern": "^[A-Z]{3}$", "maxLength": 3},
        "count": {"type": "integer", "minimum": 0},
    },
    "required": ["origin", "destination", "count"],
    "additionalProperties": False,
}

BASELINE_SCHEMA: Final = {
    "type": "object",
    "properties": {
        "rows": {
            "type": "array",
            "minItems": 1,
            "maxItems": MAX_ROWS,
            "items": BASELINE_ROW_SCHEMA,
        },
        "source_digest": {"type": "string", "maxLength": 200},
    },
    "required": ["rows"],
    "additionalProperties": False,
}

EXAMPLE_BASELINE: Final = {
    "rows": [
        {"origin": "ABE", "destination": "ATL", "count": 853},
        {"origin": "ABE", "destination": "BHM", "count": 1},
    ],
    "source_digest": "sha256:prior",
}

INVALID_BASELINE_REMEDIATION: Final = (
    "Pass baseline as an object with rows: an array of objects each having exactly "
    "origin, destination, and count (3-letter airport codes and a non-negative integer). "
    f"Do not pass dataset (that is orrery/csv-url); table-fresh fetches {CURRENT_DATASET} "
    "internally on each run."
)

TOOL_SCHEMAS: Final = {
    "run": {
        "description": (
            "Freshen a bounded flight sample and compare it to a caller baseline. "
            "Input bundle: baseline (object with rows for table-diff). "
            "Returns signed fresh-verdict Envelope chain "
            "(dispositions: ready | not-ready | stale | blocked)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "baseline": BASELINE_SCHEMA,
            },
            "required": ["baseline"],
            "additionalProperties": False,
        },
    }
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
