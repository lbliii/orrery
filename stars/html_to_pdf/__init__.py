"""html-to-pdf — framework-neutral conversion metadata and service.

Import :mod:`stars.html_to_pdf.skill` only when mounting the Chirp/MCP adapter.
"""

from .contract import STAR_NAME, STAR_VERSION, tool_schemas
from .service import convert, health

__all__ = ["STAR_NAME", "STAR_VERSION", "convert", "health", "tool_schemas"]
