"""Pricing — catalog-label honesty for the public sky."""

from __future__ import annotations

from chirp import Page


def get() -> Page:
    return Page(
        "pricing/page.html",
        "content",
        page_block_name="content",
        page_title="Pricing — Orrery",
        footer_note="Orrery · pricing",
        footer_meta="catalog label · not a forever promise",
    )
