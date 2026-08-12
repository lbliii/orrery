"""Product overview — marketer door for the gaze→resolve→call→seal loop."""

from __future__ import annotations

from chirp import Page

from discovery import TEACHING_TRIO


def get() -> Page:
    return Page(
        "product/page.html",
        "content",
        page_block_name="content",
        page_title="Product — Orrery",
        footer_note="Orrery · product",
        footer_meta="gaze → resolve → call → seal",
        teaching_trio=list(TEACHING_TRIO),
    )
