"""Connect — point an MCP client at Orrery."""

from __future__ import annotations

import json

from chirp import Page, Request

from catalog.sample import highlight_json
from discovery import (
    KIDA_DEMO,
    MCP_TOOLS,
    SLIM_MCP_COPY,
    STARTER_PATHS,
    TEACHING_TRIO,
    configured_public_origin,
    kida_demo_payload,
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
        starter_paths_html=_sample_code(highlight_json(starter_paths_payload())),
        kida_demo=list(KIDA_DEMO),
        kida_demo_json=json.dumps(kida_demo_payload(), indent=2),
        kida_demo_html=_sample_code(highlight_json(kida_demo_payload())),
        tools=[{"name": t["name"], "description": t["description"]} for t in MCP_TOOLS],
    )


def _sample_code(html: str) -> str:
    """Inner ``<code>`` of a highlight_* sample, for a template ``<pre class="sample">``."""
    start = html.find("<code")
    end = html.rfind("</code>")
    if start == -1 or end == -1:
        return html
    return html[start : end + len("</code>")]
