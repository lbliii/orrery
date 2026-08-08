"""Gaze — MCP browse/route across public sky and namespace nodes.

Progressive-disclosure discovery (Alpine-driven demo data for now; later epics
wire this to live ``gaze`` MCP nodes). Backs GitHub epic #3 (Gaze).
"""

from __future__ import annotations

from chirp import Page


def get() -> Page:
    return Page(
        "gaze/page.html",
        "content",
        page_block_name="content",
        page_title="Gaze — Orrery",
        footer_note="Gaze nodes",
    )
