"""Receipts — plain-language explainer for sealed Envelopes."""

from __future__ import annotations

from chirp import Page


def get() -> Page:
    return Page(
        "receipts/page.html",
        "content",
        page_block_name="content",
        page_title="Receipts — Orrery",
    )
