"""Human copy for namespace create page errors (#433, design #428).

Maps known ``body.error`` codes to one sentence plus a next action. JSON
``error`` keys stay snake_case; this module never substitutes them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_MACHINE_CODE = re.compile(r"^[a-z][a-z0-9_]*$")

KNOWN: dict[str, dict[str, str]] = {
    "invalid_slug": {
        "message": "That id is not a valid namespace slug.",
        "next": "Use a lowercase DNS label, 2-63 characters, starting with a letter.",
    },
    "reserved_slug": {
        "message": "That id is reserved.",
        "next": "Pick a different slug: orrery, public, and system are taken.",
    },
    "duplicate_namespace": {
        "message": "That namespace already exists.",
        "next": "Pick a different id, or resolve the existing prefix in Gaze.",
    },
}

GENERIC_MESSAGE = "Namespace could not be created."
GENERIC_NEXT = "Check the id and try a different slug."


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
