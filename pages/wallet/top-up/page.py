"""Wallet top-up — prepaid balance packs via Stripe Checkout (ADR 0003)."""

from __future__ import annotations

from chirp import Page, Request

from commerce import TOPUP_PACKS, get_ledger, wallet_enabled
from commerce.errors import TOP_UP_URL, format_usd


def get(request: Request) -> Page:
    owner_id = (request.query.get("owner_id") or "").strip()
    balance_cents: int | None = None
    if owner_id and wallet_enabled():
        balance_cents = get_ledger().get_account(owner_id).balance_cents

    packs = tuple(
        {"key": key, "label": format_usd(cents), "cents": cents}
        for key, cents in TOPUP_PACKS.items()
    )

    return Page(
        "wallet/top-up/page.html",
        "content",
        page_block_name="content",
        page_title="Wallet top-up — Orrery",
        footer_note="Orrery · wallet",
        footer_meta="prepaid balance · not per-call Stripe",
        owner_id=owner_id,
        balance_cents=balance_cents,
        balance_display=format_usd(balance_cents) if balance_cents is not None else None,
        wallet_live=wallet_enabled(),
        packs=packs,
        top_up_url=TOP_UP_URL,
        checkout_api="/api/wallet/stripe/checkout",
    )
