"""Human copy for wallet checkout page errors (#433, design #428, #477).

Maps known form/query ``error`` codes to one sentence plus a next action.
JSON ``error`` keys stay snake_case; this module never substitutes them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_MACHINE_CODE = re.compile(r"^[a-z][a-z0-9_]*$")

KNOWN: dict[str, dict[str, str]] = {
    "owner_id_required": {
        "message": "Checkout needs a wallet owner id.",
        "next": "Enter owner_id above, then start Checkout again.",
    },
    "invalid_pack": {
        "message": "That pack is not on the list.",
        "next": "Choose starter, standard, or premium, then start Checkout again.",
    },
    "wallet_disabled": {
        "message": "Prepaid wallet is off in this environment.",
        "next": "Enable the ledger on this host, or skip top-up until wallet is live.",
    },
}

GENERIC_MESSAGE = "Checkout could not start."
GENERIC_NEXT = "Check owner_id and pack, then retry."


@dataclass(frozen=True)
class PageErrorCopy:
    message: str
    next: str
    code: str

    @property
    def human_line(self) -> str:
        return f"{self.message} {self.next}".strip()


def describe(error: object) -> PageErrorCopy:
    """Return page copy for an API ``error`` value. Never echoes ``str(exc)``."""
    code = error if isinstance(error, str) else ""
    known = KNOWN.get(code)
    if known is not None:
        return PageErrorCopy(known["message"], known["next"], code)
    show = code if _MACHINE_CODE.fullmatch(code) else ""
    return PageErrorCopy(GENERIC_MESSAGE, GENERIC_NEXT, show)
