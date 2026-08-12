"""Wire envelope verify to prepaid ledger (ADR 0002) with stub fallback."""

from __future__ import annotations

import logging
import os
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from commerce.ledger import HoldStatus, WalletLedger
from commerce.stubs import charge_on_verify as _stub_charge_on_verify
from commerce.stubs import refund_on_forge as _stub_refund_on_forge

logger = logging.getLogger("orrery.commerce")

_PRICE_RE = re.compile(r"[\d.]+")
_ledger: WalletLedger | None = None


def wallet_enabled() -> bool:
    """True when ``ORRERY_WALLET_ENABLED`` opts into the real ledger."""
    return os.environ.get("ORRERY_WALLET_ENABLED", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def get_ledger() -> WalletLedger:
    """Return the process-wide in-memory ledger."""
    global _ledger
    if _ledger is None:
        _ledger = WalletLedger()
    return _ledger


def reset_ledger(ledger: WalletLedger | None = None) -> WalletLedger:
    """Replace the process-wide ledger (tests)."""
    global _ledger
    _ledger = ledger if ledger is not None else WalletLedger()
    return _ledger


def parse_price_per_call_cents(price: str | None) -> int | None:
    """Parse catalog / receipt ``price_per_call`` strings into integer cents."""
    if price is None:
        return None
    text = price.strip()
    if not text or text.lower() == "free":
        return None
    match = _PRICE_RE.search(text.replace(",", ""))
    if match is None:
        return None
    try:
        dollars = Decimal(match.group())
    except InvalidOperation:
        return None
    cents = int(dollars * 100)
    return cents if cents > 0 else None


def _is_paid_path(payment_id: str | None, price_per_call: str | None) -> bool:
    return bool(payment_id) and parse_price_per_call_cents(price_per_call) is not None


def _resolve_owner_id(payment_id: str, owner_id: str | None) -> str | None:
    if owner_id:
        return owner_id
    hold = get_ledger().find_hold(payment_id)
    return hold.owner_id if hold is not None else None


def _base_fields(
    *,
    payment_id: str | None,
    price_per_call: str | None,
    skill: str | None,
    nonce: str | None,
    reason: str,
) -> dict[str, Any]:
    return {
        "payment_id": payment_id,
        "price_per_call": price_per_call,
        "skill": skill,
        "nonce": nonce,
        "reason": reason,
    }


def charge_on_verify(
    *,
    payment_id: str | None,
    price_per_call: str | None,
    skill: str | None = None,
    nonce: str | None = None,
    reason: str = "envelope_verified",
    owner_id: str | None = None,
) -> dict[str, Any]:
    """Capture an open hold on verify-ok, or fall back to loud stubs."""
    if not wallet_enabled():
        return _stub_charge_on_verify(
            payment_id=payment_id,
            price_per_call=price_per_call,
            skill=skill,
            nonce=nonce,
            reason=reason,
        )

    fields = _base_fields(
        payment_id=payment_id,
        price_per_call=price_per_call,
        skill=skill,
        nonce=nonce,
        reason=reason,
    )
    if not _is_paid_path(payment_id, price_per_call):
        return {
            **fields,
            "action": "charge",
            "stub": False,
            "status": "skipped",
            "reason": "free_or_unpriced",
        }

    assert payment_id is not None
    resolved_owner = _resolve_owner_id(payment_id, owner_id)
    if resolved_owner is None:
        logger.warning(
            "commerce.capture_no_hold payment_id=%s price_per_call=%s skill=%s",
            payment_id,
            price_per_call,
            skill,
        )
        return {
            "action": "charge",
            "stub": False,
            "status": "hold_not_found",
            **fields,
        }

    entry = get_ledger().capture(resolved_owner, idempotency_key=payment_id)
    hold = get_ledger().find_hold(payment_id)
    logger.info(
        "commerce.captured payment_id=%s owner_id=%s entry_id=%s hold_status=%s",
        payment_id,
        resolved_owner,
        entry.id,
        hold.status if hold is not None else None,
    )
    return {
        "action": "charge",
        "stub": False,
        "status": "captured",
        "ledger_op": entry.op,
        "entry_id": entry.id,
        "hold_status": hold.status if hold is not None else HoldStatus.CAPTURED,
        **fields,
    }


def refund_on_forge(
    *,
    payment_id: str | None,
    price_per_call: str | None,
    skill: str | None = None,
    nonce: str | None = None,
    reason: str = "envelope_forge_or_fail",
    owner_id: str | None = None,
) -> dict[str, Any]:
    """Release an open hold on forge/fail, or fall back to loud stubs."""
    if not wallet_enabled():
        return _stub_refund_on_forge(
            payment_id=payment_id,
            price_per_call=price_per_call,
            skill=skill,
            nonce=nonce,
            reason=reason,
        )

    fields = _base_fields(
        payment_id=payment_id,
        price_per_call=price_per_call,
        skill=skill,
        nonce=nonce,
        reason=reason,
    )
    if not _is_paid_path(payment_id, price_per_call):
        return {
            **fields,
            "action": "refund",
            "stub": False,
            "status": "skipped",
            "reason": "free_or_unpriced",
        }

    assert payment_id is not None
    resolved_owner = _resolve_owner_id(payment_id, owner_id)
    if resolved_owner is None:
        logger.warning(
            "commerce.release_no_hold payment_id=%s price_per_call=%s skill=%s",
            payment_id,
            price_per_call,
            skill,
        )
        return {
            "action": "refund",
            "stub": False,
            "status": "hold_not_found",
            **fields,
        }

    entry = get_ledger().release(resolved_owner, idempotency_key=payment_id)
    hold = get_ledger().find_hold(payment_id)
    logger.info(
        "commerce.released payment_id=%s owner_id=%s entry_id=%s hold_status=%s",
        payment_id,
        resolved_owner,
        entry.id,
        hold.status if hold is not None else None,
    )
    return {
        "action": "refund",
        "stub": False,
        "status": "released",
        "ledger_op": entry.op,
        "entry_id": entry.id,
        "hold_status": hold.status if hold is not None else HoldStatus.RELEASED,
        **fields,
    }
