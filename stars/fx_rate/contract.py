"""Stable contract for offline allowlisted FX as-of lookup."""

from __future__ import annotations

from typing import Final

from .rates import PAIRS, PINNED_AS_OF

STAR_NAME: Final = "orrery/fx-rate"
STAR_VERSION: Final = "0.1.0"
DEFAULT_PAIR: Final = "usd-eur"
DEFAULT_AS_OF: Final = "2026-06-01"

TOOL_SCHEMAS: Final = {
    "fx_rate": {
        "description": "Look up an allowlisted FX pair at a pinned as-of date.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pair": {
                    "type": "string",
                    "enum": sorted(PAIRS),
                    "description": "Allowlisted base-quote token (e.g. usd-eur).",
                },
                "as_of": {
                    "type": "string",
                    "format": "date",
                    "enum": sorted(PINNED_AS_OF),
                    "description": "Pinned calendar date for the fixture revision.",
                },
            },
            "required": ["pair", "as_of"],
        },
    },
    "answer": {
        "description": "FX rate lookup with a concise answer sealed in an Envelope.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pair": {
                    "type": "string",
                    "enum": sorted(PAIRS),
                    "default": DEFAULT_PAIR,
                },
                "as_of": {
                    "type": "string",
                    "format": "date",
                    "enum": sorted(PINNED_AS_OF),
                    "default": DEFAULT_AS_OF,
                },
            },
        },
    },
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
