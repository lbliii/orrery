"""Stable contract for static public-holiday lookup."""

from __future__ import annotations

from typing import Final

from .dataset import PINNED_YEARS, REGIONS

STAR_NAME: Final = "orrery/holidays"
STAR_VERSION: Final = "0.1.0"
DEFAULT_REGION: Final = "US"
DEFAULT_YEAR: Final = 2026

TOOL_SCHEMAS: Final = {
    "list": {
        "description": "List public holidays for an allowlisted region code and pinned year.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "region": {
                    "type": "string",
                    "enum": sorted(REGIONS),
                    "default": DEFAULT_REGION,
                    "description": "ISO 3166-1 alpha-2 region code from the allowlist.",
                },
                "year": {
                    "type": "integer",
                    "enum": sorted(PINNED_YEARS),
                    "default": DEFAULT_YEAR,
                    "description": "Calendar year from the pinned dataset revision.",
                },
            },
        },
    },
    "answer": {
        "description": "Return a concise holiday summary sealed in an Envelope.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "region": {
                    "type": "string",
                    "enum": sorted(REGIONS),
                    "default": DEFAULT_REGION,
                },
                "year": {
                    "type": "integer",
                    "enum": sorted(PINNED_YEARS),
                    "default": DEFAULT_YEAR,
                },
            },
        },
    },
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
