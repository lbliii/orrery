"""Stable contract for offline allowlisted flight status lookup."""

from __future__ import annotations

from typing import Final

from .flights import FLIGHT_IDS, PINNED_DATES

STAR_NAME: Final = "orrery/flight-status"
STAR_VERSION: Final = "0.1.0"
DEFAULT_FLIGHT: Final = "AA100"
DEFAULT_DATE: Final = "2026-08-11"

TOOL_SCHEMAS: Final = {
    "status": {
        "description": "Resolve an allowlisted flight id and date to schedule/status fields.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "flight": {
                    "type": "string",
                    "enum": FLIGHT_IDS,
                    "description": "Named allowlisted flight fixture (no arbitrary lookup).",
                },
                "date": {
                    "type": "string",
                    "enum": PINNED_DATES,
                    "description": "ISO date from the pinned fixture schedule.",
                },
            },
            "required": ["flight", "date"],
        },
    },
    "answer": {
        "description": "Return flight status and a concise answer sealed in an Envelope.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "flight": {
                    "type": "string",
                    "enum": FLIGHT_IDS,
                    "default": DEFAULT_FLIGHT,
                },
                "date": {
                    "type": "string",
                    "enum": PINNED_DATES,
                    "default": DEFAULT_DATE,
                },
            },
        },
    },
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
