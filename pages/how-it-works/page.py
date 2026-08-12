"""How it works — gaze → resolve → call → seal with proof pointers."""

from __future__ import annotations

from chirp import Page

from discovery import DIRECT_STAR_ENDPOINTS, TEACHING_TRIO


def get() -> Page:
    return Page(
        "how-it-works/page.html",
        "content",
        page_block_name="content",
        page_title="How it works — Orrery",
        footer_note="Orrery · architecture",
        footer_meta="gaze → resolve → call → seal",
        teaching_trio=list(TEACHING_TRIO),
        direct_endpoints=list(DIRECT_STAR_ENDPOINTS),
    )
