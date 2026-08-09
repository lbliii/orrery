"""Stable Source Watch contract and JSON-schema projections.

This module is deliberately independent of Chirp and HTTP.  Hosts can use the
same metadata for MCP discovery, receipts, documentation, fixtures, and tests.
"""

from __future__ import annotations

from typing import Final, TypedDict

STAR_NAME: Final = "orrery/source-watch"
STAR_VERSION: Final = "0.1.0"
DEFAULT_SOURCE: Final = "python-release-notes"
ANSWER_MAX_CHARS: Final = 1_200


class ObserveInput(TypedDict, total=False):
    source: str


class DiffInput(ObserveInput, total=False):
    since_digest: str


class AnswerInput(ObserveInput, total=False):
    question: str
    max_chars: int


SOURCE_SCHEMA: Final = {
    "type": "string",
    "default": DEFAULT_SOURCE,
    "description": "Allowlisted Source Watch source identifier.",
}

TOOL_SCHEMAS: Final = {
    "observe": {
        "description": "Fetch an allowlisted source and record digest evidence.",
        "inputSchema": {"type": "object", "properties": {"source": SOURCE_SCHEMA}},
    },
    "diff": {
        "description": "Fetch now and compare normalized content to a known digest.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": SOURCE_SCHEMA,
                "since_digest": {"type": "string", "default": ""},
            },
        },
    },
    "answer": {
        "description": "Return a bounded extractive answer with fresh source evidence.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "source": SOURCE_SCHEMA,
                "max_chars": {"type": "integer", "minimum": 1, "maximum": ANSWER_MAX_CHARS},
            },
            "required": ["question"],
        },
    },
}


def tool_schemas() -> dict[str, object]:
    """Return a copy-safe projection of the public, canonical tool contract."""
    # The projection contains only JSON primitives, so a shallow reconstruction
    # avoids exposing mutable nested dictionaries owned by this module.
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
