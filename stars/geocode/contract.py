"""Stable contract for offline allowlisted place geocoding."""

from __future__ import annotations

from typing import Final

from .places import PLACES

STAR_NAME: Final = "orrery/geocode"
STAR_VERSION: Final = "0.1.0"
DEFAULT_PLACE: Final = "new-york"

TOOL_SCHEMAS: Final = {
    "geocode": {
        "description": "Resolve an allowlisted place token to coordinates and display name.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "place": {
                    "type": "string",
                    "enum": sorted(PLACES),
                    "description": "Named allowlisted place fixture (no arbitrary geocoding).",
                },
            },
            "required": ["place"],
        },
    },
    "answer": {
        "description": "Geocode a place token and return a concise answer sealed in an Envelope.",
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
