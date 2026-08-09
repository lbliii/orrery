"""World Time — framework-neutral live UTC behavior.

Import :mod:`stars.world_time.skill` only when mounting the Chirp/MCP adapter.
"""

from .contract import STAR_NAME, STAR_VERSION, tool_schemas
from .service import answer, fetch, fetch_live_utc, get

__all__ = [
    "STAR_NAME",
    "STAR_VERSION",
    "answer",
    "fetch",
    "fetch_live_utc",
    "get",
    "tool_schemas",
]
