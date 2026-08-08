"""Commerce hooks — pricing stubs today, prepaid wallet later (Wave 2).

Real ledger / Stripe live in design ADRs (``docs/adr/``). This package only
exposes **loud** charge-on-verify / refund-on-forge stubs so agents never hit
silent no-ops (GitHub #35).
"""

from .stubs import charge_on_verify, refund_on_forge

__all__ = ["charge_on_verify", "refund_on_forge"]
