"""Source Watch — a self-contained, evidence-backed Star package.

The package root intentionally exposes only framework-neutral behavior.  Import
``stars.source_watch.skill`` when a Chirp/MCP adapter is required.
"""

from .contract import ANSWER_MAX_CHARS, STAR_NAME, STAR_VERSION, tool_schemas
from .service import answer, diff, observe

__all__ = [
    "ANSWER_MAX_CHARS",
    "STAR_NAME",
    "STAR_VERSION",
    "answer",
    "diff",
    "observe",
    "tool_schemas",
]
