"""Namespaces — the private "company Skill DNS" pitch (SaaS wedge).

Create flow posts to ``POST /api/namespaces`` (#383). Backs GitHub epic #6
(Namespaces).
"""

from __future__ import annotations

from chirp import Page


def get() -> Page:
    return Page(
        "namespaces/page.html",
        "content",
        page_block_name="content",
        page_title="Private namespaces — Orrery",
        footer_note="Private namespaces",
        footer_meta="public free · namespace paid",
        create_api="/api/namespaces",
    )
