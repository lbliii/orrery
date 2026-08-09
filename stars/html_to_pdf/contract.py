"""Stable html-to-pdf contract and JSON-schema projections."""

from __future__ import annotations

from typing import Final, TypedDict

STAR_NAME: Final = "orrery/html-to-pdf"
STAR_VERSION: Final = "1.2.0"


class ConvertInput(TypedDict):
    html: str


TOOL_SCHEMAS: Final = {
    "convert": {
        "description": "Render simple HTML to a short-lived downloadable PDF with checksums.",
        "inputSchema": {
            "type": "object",
            "properties": {"html": {"type": "string"}},
            "required": ["html"],
        },
    },
    "health": {
        "description": "html-to-pdf readiness probe.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "submit": {
        "description": "Queue a managed PDF run and return its run ID.",
        "inputSchema": {
            "type": "object",
            "properties": {"html": {"type": "string"}, "idempotency_key": {"type": "string"}},
            "required": ["html", "idempotency_key"],
        },
    },
    "result": {
        "description": "Return queued state or the signed final receipt for a managed run.",
        "inputSchema": {
            "type": "object",
            "properties": {"run_id": {"type": "string"}},
            "required": ["run_id"],
        },
    },
}


def tool_schemas() -> dict[str, object]:
    """Return a copy-safe projection of the public tool contract."""
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
