"""Stable contract for offline timezone resolution."""

from __future__ import annotations

from typing import Final

from .lookup import PLACES

STAR_NAME: Final = "orrery/tz-resolve"
STAR_VERSION: Final = "0.1.0"
DEFAULT_PLACE: Final = "new-york"

TOOL_SCHEMAS: Final = {
    "resolve": {
        "description": (
            "Resolve an allowlisted place token or lat/lon pair to an IANA timezone."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "place": {
                    "type": "string",
                    "enum": sorted(PLACES),
                    "description": "Named allowlisted place fixture (no arbitrary geocoding).",
                },
                "latitude": {
                    "type": "number",
                    "minimum": -90,
                    "maximum": 90,
                    "description": "Latitude in decimal degrees.",
                },
                "longitude": {
                    "type": "number",
                    "minimum": -180,
                    "maximum": 180,
                    "description": "Longitude in decimal degrees.",
                },
            },
        },
    },
    "answer": {
        "description": "Resolve timezone and return a concise answer sealed in an Envelope.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "place": {
                    "type": "string",
                    "enum": sorted(PLACES),
                    "default": DEFAULT_PLACE,
                },
            },
        },
    },
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
