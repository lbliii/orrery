"""For harnesses — tree-handling rim in public language."""

from __future__ import annotations

from chirp import Page


def get() -> Page:
    return Page(
        "for-harnesses/page.html",
        "content",
        page_block_name="content",
        page_title="For harnesses — Orrery",
        footer_note="Orrery · for harnesses",
        footer_meta="hang sealed leaves · not swarm VCS",
    )
