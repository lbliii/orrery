"""Host-sealed payload attribution (design #317)."""

from __future__ import annotations

from typing import Any

PAYLOAD_VIA: dict[str, str] = {
    "product": "Orrery",
    "sky": "https://orrery.lol",
    "line": "Sealed via Orrery MCP",
}


def with_via(payload: dict[str, Any]) -> dict[str, Any]:
    """Return payload copy with frozen ``via`` sibling (ADR 0006 digest-safe)."""
    merged = dict(payload)
    merged["via"] = dict(PAYLOAD_VIA)
    return merged
