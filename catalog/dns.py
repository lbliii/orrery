"""Skill DNS host identity for ``mcp://`` resolve endpoints.

The HTTP surface is ``https://orrery.lol``; Skill DNS uses the same apex as
``mcp://orrery.lol/…`` (and ``mcp://{tenant}.orrery.lol/…`` for namespaces).
Override with ``ORRERY_MCP_HOST`` for local / staging forks.
"""

from __future__ import annotations

import os

DEFAULT_MCP_HOST = "orrery.lol"


def mcp_host() -> str:
    """Return the Skill DNS apex host (no scheme)."""
    return (os.environ.get("ORRERY_MCP_HOST") or DEFAULT_MCP_HOST).strip() or DEFAULT_MCP_HOST


def mcp_url(path: str, *, namespace: str | None = None) -> str:
    """Build an ``mcp://`` Skill DNS URL for ``path`` (must start with ``/``)."""
    host = mcp_host()
    if namespace:
        host = f"{namespace.strip()}.{host}"
    if not path.startswith("/"):
        path = f"/{path}"
    return f"mcp://{host}{path}"
