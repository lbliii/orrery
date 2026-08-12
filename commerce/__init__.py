"""Commerce hooks — ledger-backed verify wiring with stub fallback (Wave 2).

Real Stripe top-up lives in ADR 0003. Verify paths use the prepaid ledger when
``ORRERY_WALLET_ENABLED`` is set; otherwise loud stubs remain (GitHub #35).
"""

from .errors import InsufficientBalanceError
from .ledger import Hold, HoldStatus, LedgerEntry, LedgerOp, WalletAccount, WalletLedger
from .verify_wire import charge_on_verify, get_ledger, refund_on_forge, reset_ledger, wallet_enabled

__all__ = [
    "Hold",
    "HoldStatus",
    "InsufficientBalanceError",
    "LedgerEntry",
    "LedgerOp",
    "WalletAccount",
    "WalletLedger",
    "charge_on_verify",
    "get_ledger",
    "refund_on_forge",
    "reset_ledger",
    "wallet_enabled",
]
