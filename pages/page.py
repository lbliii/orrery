"""Landing — brand hero, the gaze/resolve/call story, and a live feed.

The below-fold activity strip subscribes to ``/feed`` (SSE) so every MCP
``tools/call`` against the aggregated host appears in real time.
"""

from __future__ import annotations

from chirp import Page

from dogfood import N_DOGFOOD_SKILLS


def get() -> Page:
    return Page(
        "page.html",
        "content",
        page_block_name="content",
        page_title="Orrery — skills you point at",
        footer_note="Orrery · live host",
        skill_count=N_DOGFOOD_SKILLS,
        mcp_path="/mcp",
    )
