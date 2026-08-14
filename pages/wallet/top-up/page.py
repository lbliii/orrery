"""Wallet top-up — prepaid balance packs via Stripe Checkout (ADR 0003)."""

from __future__ import annotations

from urllib.parse import quote

from chirp import Page, Redirect, Request, Response, ValidationError, hx_redirect

from commerce import TOPUP_PACKS, create_checkout_session, get_ledger, wallet_enabled
from commerce.errors import TOP_UP_URL, format_usd
from pages.wallet._errors import PageErrorCopy, describe

_TOP_UP = "/wallet/top-up"
_CHECKOUT_API = "/api/wallet/stripe/checkout"
_DEFAULT_PACK = "starter"


def _packs() -> tuple[dict[str, object], ...]:
    return tuple(
        {"key": key, "label": format_usd(cents), "cents": cents}
        for key, cents in TOPUP_PACKS.items()
    )


def _selected_pack(raw: str) -> str:
    key = raw.strip().lower()
    return key if key in TOPUP_PACKS else _DEFAULT_PACK


def _checkout_ctx(
    *,
    owner_id: str = "",
    selected: str = _DEFAULT_PACK,
    error: PageErrorCopy | None = None,
) -> dict[str, object]:
    return {
        "owner_id": owner_id,
        "selected": selected,
        "error": error,
        "packs": _packs(),
        "checkout_api": _CHECKOUT_API,
    }


def _page(
    *,
    owner_id: str = "",
    selected: str = _DEFAULT_PACK,
    error: PageErrorCopy | None = None,
    balance_cents: int | None = None,
) -> Page:
    return Page(
        "wallet/top-up/page.html",
        "checkout_panel",
        page_block_name="content",
        page_title="Wallet top-up — Orrery",
        footer_note="Orrery · wallet",
        footer_meta="prepaid balance · not per-call Stripe",
        balance_cents=balance_cents,
        balance_display=(
            format_usd(balance_cents) if balance_cents is not None else None
        ),
        wallet_live=wallet_enabled(),
        top_up_url=TOP_UP_URL,
        **_checkout_ctx(owner_id=owner_id, selected=selected, error=error),
    )


def _error_redirect(error: PageErrorCopy, owner_id: str, pack: str) -> Redirect:
    token = error.code or "-"
    query = f"error={quote(token, safe='')}"
    if owner_id:
        query += f"&owner_id={quote(owner_id, safe='')}"
    if pack:
        query += f"&pack={quote(pack, safe='')}"
    return Redirect(f"{_TOP_UP}?{query}", status=303)


def _fail(
    request: Request, code: str, owner_id: str, pack: str
) -> ValidationError | Redirect:
    error = describe(code)
    selected = _selected_pack(pack)
    if request.is_htmx:
        return ValidationError(
            "wallet/top-up/page.html",
            "checkout_panel",
            **_checkout_ctx(owner_id=owner_id, selected=selected, error=error),
        )
    return _error_redirect(error, owner_id, pack)


def get(request: Request) -> Page:
    owner_id = (request.query.get("owner_id") or "").strip()
    selected = _selected_pack(request.query.get("pack") or "")
    raw_error = (request.query.get("error") or "").strip()
    error = describe(raw_error) if raw_error else None
    balance_cents: int | None = None
    if owner_id and wallet_enabled():
        balance_cents = get_ledger().get_account(owner_id).balance_cents
    return _page(
        owner_id=owner_id,
        selected=selected,
        error=error,
        balance_cents=balance_cents,
    )


async def post(request: Request) -> Response | Redirect | ValidationError:
    form = await request.form()
    raw_owner = form.get("owner_id")
    owner_id = raw_owner.strip() if isinstance(raw_owner, str) else ""
    raw_pack = form.get("pack")
    pack = raw_pack.strip() if isinstance(raw_pack, str) else ""

    if not owner_id:
        return _fail(request, "owner_id_required", owner_id, pack)
    if pack not in TOPUP_PACKS:
        return _fail(request, "invalid_pack", owner_id, pack)
    if not wallet_enabled():
        return _fail(request, "wallet_disabled", owner_id, pack)
    try:
        session = create_checkout_session(owner_id=owner_id, pack=pack)
    except (ValueError, RuntimeError):
        return _fail(request, "", owner_id, pack)
    url = session.get("url")
    if not isinstance(url, str) or not url.strip():
        return _fail(request, "", owner_id, pack)
    return hx_redirect(url)
