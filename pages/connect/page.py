"""Connect — point an MCP client at Orrery."""

from __future__ import annotations

import json

from chirp import Page, Request

from discovery import (
    MCP_TOOLS,
    SLIM_MCP_COPY,
    STARTER_PATHS,
    TEACHING_TRIO,
    configured_public_origin,
    mcp_endpoint,
    resolve_public_origin,
    starter_paths_payload,
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
        slim_mcp_copy=SLIM_MCP_COPY,
        teaching_trio=list(TEACHING_TRIO),
        starter_paths=list(STARTER_PATHS),
        starter_paths_json=json.dumps(starter_paths_payload(), indent=2),
        tools=[{"name": t["name"], "description": t["description"]} for t in MCP_TOOLS],
    )
