"""FX rate as-of — static pinned fixtures for allowlisted currency pairs."""

from .contract import STAR_NAME, STAR_VERSION, tool_schemas
from .service import answer, fx_rate

__all__ = ["STAR_NAME", "STAR_VERSION", "answer", "fx_rate", "tool_schemas"]
