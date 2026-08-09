"""Connect — point an MCP client at Orrery."""

from __future__ import annotations

from chirp import Page, Request

from discovery import (
    MCP_TOOLS,
    configured_public_origin,
    mcp_endpoint,
    resolve_public_origin,
)


def get(request: Request) -> Page:
    origin = resolve_public_origin(configured_public_origin(), request.url)
    return Page(
        "connect/page.html",
        "content",
        page_block_name="content",
        page_title="Connect — Orrery",
        footer_note="Orrery · connect",
        footer_meta="point → call → seal",
        origin=origin,
        mcp_url=mcp_endpoint(origin),
        tools=[{"name": t["name"], "description": t["description"]} for t in MCP_TOOLS],
    )
