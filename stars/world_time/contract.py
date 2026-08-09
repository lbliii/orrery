"""Stable World Time contract and JSON-schema projections."""

from __future__ import annotations

from typing import Final

STAR_NAME: Final = "orrery/world-time"
STAR_VERSION: Final = "0.1.0"
WORLD_TIME_URL: Final = "https://timeapi.io/api/Time/current/zone?timeZone=UTC"
FALLBACK_TIME_URL: Final = "https://www.google.com/generate_204"
CLONE_WARNING: Final = (
    "Offline clones cannot mint a fresh UTC instant from the public clock API; "
    "any baked-in datetime is stale by definition. Value is live truth at call time."
)

TOOL_SCHEMAS: Final = {
    "fetch": {
        "description": "Fetch live UTC from the public clock API (signed at call time).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "get": {
        "description": "Get the live UTC reading (same live source as fetch).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "answer": {
        "description": "Answer with the live UTC datetime sealed in an Envelope.",
        "inputSchema": {"type": "object", "properties": {}},
    },
}


def tool_schemas() -> dict[str, object]:
    """Return a copy-safe projection of the public tool contract."""
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
