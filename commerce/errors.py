"""Structured commerce errors (ADR 0002)."""

from __future__ import annotations

TOP_UP_URL = "https://orrery.lol/wallet/top-up"


def format_usd(cents: int) -> str:
    """Format integer cents as a USD display string (e.g. ``$1.00``)."""
    return f"${cents / 100:.2f}"


class InsufficientBalanceError(Exception):
    """Spendable balance is below the hold price (no Stripe call)."""

    def __init__(self, *, price_per_call_cents: int, balance_cents: int) -> None:
        self.price_per_call_cents = price_per_call_cents
        self.balance_cents = balance_cents
        super().__init__(
            f"insufficient balance: need {price_per_call_cents}c, have {balance_cents}c"
        )

    def to_dict(self) -> dict[str, int | str]:
        return {
            "code": "insufficient_balance",
            "price_per_call": format_usd(self.price_per_call_cents),
            "price_per_call_cents": self.price_per_call_cents,
            "balance": format_usd(self.balance_cents),
            "balance_cents": self.balance_cents,
            "top_up_url": TOP_UP_URL,
        }


class HoldNotFoundError(Exception):
    """No hold exists for the given payment / idempotency key."""

    def __init__(self, idempotency_key: str) -> None:
        self.idempotency_key = idempotency_key
        super().__init__(f"hold not found for key {idempotency_key!r}")


class InvalidHoldTransitionError(Exception):
    """Hold cannot move to the requested terminal state."""

    def __init__(self, idempotency_key: str, status: str, op: str) -> None:
        self.idempotency_key = idempotency_key
        self.status = status
        self.op = op
        super().__init__(f"cannot {op} hold {idempotency_key!r} in status {status!r}")
