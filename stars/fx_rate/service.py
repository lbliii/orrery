"""Offline allowlisted FX pair + as-of date → rate for quote joins."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from .contract import DEFAULT_AS_OF, DEFAULT_PAIR
from .rates import PAIRS, PINNED_AS_OF, rate_for

PROVIDER = "orrery-fixtures"
SOURCE = "static:orrery/fx-rate-v1"


def fx_rate(
    *,
    pair: str,
    as_of: str,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    """Return the pinned FX rate for an allowlisted pair and as-of date."""
    observed_at = (clock or (lambda: datetime.now(UTC)))().isoformat()
    token = str(pair).strip().lower()
    if not token:
        return {"error": "missing_input", "live_at_call": True}
    if token not in PAIRS:
        return {
            "error": "pair_not_allowed",
            "pair": pair,
            "live_at_call": True,
        }
    date = str(as_of).strip()
    if date not in PINNED_AS_OF:
        return {
            "error": "as_of_not_available",
            "pair": token,
            "as_of": as_of,
            "pinned_as_of": sorted(PINNED_AS_OF),
            "live_at_call": True,
        }
    record = rate_for(token, date)
    if record is None:
        return {
            "error": "as_of_not_available",
            "pair": token,
            "as_of": date,
            "pinned_as_of": sorted(PINNED_AS_OF),
            "live_at_call": True,
        }
    return {
        "pair": token,
        "base": record["base"],
        "quote": record["quote"],
        "rate": record["rate"],
        "as_of": date,
        "provider": PROVIDER,
        "source": SOURCE,
        "observed_at": observed_at,
        "offline": True,
        "live_at_call": True,
    }


def answer(
    *,
    pair: str = DEFAULT_PAIR,
    as_of: str = DEFAULT_AS_OF,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    """Return a concise FX rate answer with the full lookup payload."""
    resolved = fx_rate(pair=pair, as_of=as_of, clock=clock)
    if resolved.get("error"):
        return resolved
    base = str(resolved["base"])
    quote = str(resolved["quote"])
    rate = resolved["rate"]
    date = str(resolved["as_of"])
    return {
        **resolved,
        "answer": f"1 {base} = {rate} {quote} as of {date}",
    }
