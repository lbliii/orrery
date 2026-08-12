"""Stable html-to-pdf contract and JSON-schema projections."""

from __future__ import annotations

from typing import Final, TypedDict

STAR_NAME: Final = "orrery/html-to-pdf"
STAR_VERSION: Final = "1.2.0"


class ConvertInput(TypedDict):
    html: str


TOOL_SCHEMAS: Final = {
    "convert": {
        "description": (
            "Render simple HTML to a short-lived downloadable PDF synchronously "
            "in the API process. Use for small jobs when the caller can wait."
        ),
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
        "description": (
            "Queue a managed PDF run on the private worker and return run_id plus "
            "queued state. Poll result(run_id) until state is terminal. Prefer "
            "convert for quick synchronous PDFs; use submit/result for durable "
            "worker execution."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"html": {"type": "string"}, "idempotency_key": {"type": "string"}},
            "required": ["html", "idempotency_key"],
        },
    },
    "result": {
        "description": (
            "Poll a managed run by run_id from submit. Returns queued or running "
            "state until the worker seals a signed final receipt. Unknown run_id "
            "returns {error: run_not_found, run_id}."
        ),
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
