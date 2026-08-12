"""Commerce hooks — ledger-backed verify wiring with stub fallback (Wave 2).

Real Stripe top-up lives in ADR 0003. Verify paths use the prepaid ledger when
``ORRERY_WALLET_ENABLED`` is set; otherwise loud stubs remain (GitHub #35).
"""

from .errors import InsufficientBalanceError
from .hold import HoldRequestError, WalletDisabledError, hold_to_dict, open_hold
from .ledger import Hold, HoldStatus, LedgerEntry, LedgerOp, WalletAccount, WalletLedger
from .stripe_topup import (
    TOPUP_PACKS,
    create_checkout_session,
    handle_stripe_webhook,
    reset_stripe_topup,
)
from .verify_wire import charge_on_verify, get_ledger, refund_on_forge, reset_ledger, wallet_enabled

__all__ = [
    "TOPUP_PACKS",
    "Hold",
    "HoldRequestError",
    "HoldStatus",
    "InsufficientBalanceError",
    "LedgerEntry",
    "LedgerOp",
    "WalletAccount",
    "WalletDisabledError",
    "WalletLedger",
    "charge_on_verify",
    "create_checkout_session",
    "get_ledger",
    "handle_stripe_webhook",
    "hold_to_dict",
    "open_hold",
    "refund_on_forge",
    "reset_ledger",
    "reset_stripe_topup",
    "wallet_enabled",
]
