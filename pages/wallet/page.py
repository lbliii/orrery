"""Wallet — Stripe Checkout return UX (no ledger credit from query params)."""

from __future__ import annotations

from chirp import Page, Request

from commerce.errors import TOP_UP_URL


def get(request: Request) -> Page:
    topup = (request.query.get("topup") or "").strip().lower()
    status: str | None = None
    if topup == "success":
        status = "success"
    elif topup == "cancel":
        status = "cancel"

    return Page(
        "wallet/page.html",
        "content",
        page_block_name="content",
        page_title="Wallet — Orrery",
        footer_note="Orrery · wallet",
        footer_meta="webhook credits balance · not this URL",
        topup_status=status,
        top_up_url=TOP_UP_URL,
    )
