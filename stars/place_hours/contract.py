"""Stable contract for offline allowlisted venue hours lookup."""

from __future__ import annotations

from typing import Final

from .venues import VENUES

STAR_NAME: Final = "orrery/place-hours"
STAR_VERSION: Final = "0.1.0"
DEFAULT_VENUE: Final = "central-park-cafe-nyc"

TOOL_SCHEMAS: Final = {
    "place_hours": {
        "description": "Resolve an allowlisted venue token to hours and open-now status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "venue": {
                    "type": "string",
                    "enum": sorted(VENUES),
                    "description": "Named allowlisted venue fixture (no arbitrary search).",
                },
                "as_of": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Optional ISO-8601 instant for open-now evaluation.",
                },
            },
            "required": ["venue"],
        },
    },
    "answer": {
        "description": "Venue hours lookup with a concise answer sealed in an Envelope.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "venue": {
                    "type": "string",
                    "enum": sorted(VENUES),
                    "default": DEFAULT_VENUE,
                },
                "as_of": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Optional ISO-8601 instant for open-now evaluation.",
                },
            },
        },
    },
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
