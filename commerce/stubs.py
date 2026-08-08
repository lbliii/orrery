"""Loud commerce stubs — charge on verify-ok, refund on forge/fail.

These are intentional placeholders until the prepaid wallet ledger (#38) and
Stripe top-up (#39) land. Every call logs a clear ``commerce.charge_stub`` or
``commerce.refund_stub`` line so missing wallet wiring is never silent.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("orrery.commerce")


def charge_on_verify(
    *,
    payment_id: str | None,
    price_per_call: str | None,
    skill: str | None = None,
    nonce: str | None = None,
    reason: str = "envelope_verified",
) -> dict[str, Any]:
    """Stub: burn / capture prepaid toll when Envelope verifies.

    Logs loudly; does not touch Stripe or a real ledger.
    """
    result = {
        "action": "charge",
        "stub": True,
        "status": "stub_charged",
        "payment_id": payment_id,
        "price_per_call": price_per_call,
        "skill": skill,
        "nonce": nonce,
        "reason": reason,
    }
    logger.warning(
        "commerce.charge_stub status=%s payment_id=%s price_per_call=%s "
        "skill=%s nonce=%s reason=%s",
        result["status"],
        payment_id,
        price_per_call,
        skill,
        nonce,
        reason,
    )
    return result


def refund_on_forge(
    *,
    payment_id: str | None,
    price_per_call: str | None,
    skill: str | None = None,
    nonce: str | None = None,
    reason: str = "envelope_forge_or_fail",
) -> dict[str, Any]:
    """Stub: release / refund when signature fails or Envelope is forged.

    Logs loudly; does not touch Stripe or a real ledger.
    """
    result = {
        "action": "refund",
        "stub": True,
        "status": "stub_refunded",
        "payment_id": payment_id,
        "price_per_call": price_per_call,
        "skill": skill,
        "nonce": nonce,
        "reason": reason,
    }
    logger.warning(
        "commerce.refund_stub status=%s payment_id=%s price_per_call=%s "
        "skill=%s nonce=%s reason=%s",
        result["status"],
        payment_id,
        price_per_call,
        skill,
        nonce,
        reason,
    )
    return result
