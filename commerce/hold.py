"""Public prepaid hold API (ADR 0002) — soft reserve before publisher call."""

from __future__ import annotations

from typing import Any

from commerce.errors import format_usd
from commerce.ledger import Hold
from commerce.verify_wire import get_ledger, parse_price_per_call_cents, wallet_enabled


class WalletDisabledError(Exception):
    """Hold requires ``ORRERY_WALLET_ENABLED``."""


class HoldRequestError(Exception):
    """Invalid hold request fields."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _resolve_amount_cents(
    *,
    price_per_call: str | None,
    amount_cents: int | None,
) -> int:
    if amount_cents is not None:
        if amount_cents <= 0:
            raise HoldRequestError("invalid_amount_cents")
        return amount_cents
    cents = parse_price_per_call_cents(price_per_call)
    if cents is None:
        raise HoldRequestError("price_required")
    return cents


def hold_to_dict(hold: Hold) -> dict[str, Any]:
    """Serialize a hold for HTTP responses."""
    price_cents = hold.price_per_call_cents or hold.amount_cents
    return {
        "status": hold.status,
        "hold_id": hold.hold_id,
        "payment_id": hold.idempotency_key,
        "owner_id": hold.owner_id,
        "amount_cents": hold.amount_cents,
        "price_per_call": format_usd(price_cents),
        "price_per_call_cents": price_cents,
        "hold_status": hold.status,
        "skill": hold.skill,
        "expires_at": hold.expires_at.isoformat(),
        "created_at": hold.created_at.isoformat(),
    }


def open_hold(
    *,
    owner_id: str,
    payment_id: str,
    price_per_call: str | None = None,
    amount_cents: int | None = None,
    skill: str | None = None,
) -> dict[str, Any]:
    """Open an idempotent prepaid hold keyed on ``payment_id`` (Envelope id).

    Raises ``WalletDisabledError`` when the wallet feature flag is off.
    Raises ``HoldRequestError`` for invalid input.
    Raises ``InsufficientBalanceError`` when spendable balance is too low.
    """
    if not wallet_enabled():
        raise WalletDisabledError

    owner = owner_id.strip()
    if not owner:
        raise HoldRequestError("owner_id_required")
    key = payment_id.strip()
    if not key:
        raise HoldRequestError("payment_id_required")

    cents = _resolve_amount_cents(price_per_call=price_per_call, amount_cents=amount_cents)
    ledger = get_ledger()
    hold = ledger.hold(
        owner,
        cents,
        idempotency_key=key,
        payment_id=key,
        skill=skill,
        price_per_call_cents=cents,
    )
    return hold_to_dict(hold)
