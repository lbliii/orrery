"""Pinned FX rate fixtures — no live market feed, no wallet (#111)."""

from __future__ import annotations

from typing import Final, TypedDict


class RateRecord(TypedDict):
    base: str
    quote: str
    rate: float


# Allowlisted base/quote tokens shipped in v1; expand only via explicit revision.
PAIRS: Final = frozenset({"usd-eur", "usd-gbp", "usd-jpy", "eur-gbp", "gbp-jpy", "eur-usd"})

# Pinned as-of calendar dates aligned with secretary-enrich quote joins.
PINNED_AS_OF: Final = frozenset({"2026-01-15", "2026-06-01", "2026-08-01"})

_DATASET: Final[dict[str, dict[str, RateRecord]]] = {
    "usd-eur": {
        "2026-01-15": {"base": "USD", "quote": "EUR", "rate": 0.9234},
        "2026-06-01": {"base": "USD", "quote": "EUR", "rate": 0.8812},
        "2026-08-01": {"base": "USD", "quote": "EUR", "rate": 0.8645},
    },
    "usd-gbp": {
        "2026-01-15": {"base": "USD", "quote": "GBP", "rate": 0.8011},
        "2026-06-01": {"base": "USD", "quote": "GBP", "rate": 0.7854},
        "2026-08-01": {"base": "USD", "quote": "GBP", "rate": 0.7720},
    },
    "usd-jpy": {
        "2026-01-15": {"base": "USD", "quote": "JPY", "rate": 157.42},
        "2026-06-01": {"base": "USD", "quote": "JPY", "rate": 156.88},
        "2026-08-01": {"base": "USD", "quote": "JPY", "rate": 147.35},
    },
    "eur-gbp": {
        "2026-01-15": {"base": "EUR", "quote": "GBP", "rate": 0.8674},
        "2026-06-01": {"base": "EUR", "quote": "GBP", "rate": 0.8912},
        "2026-08-01": {"base": "EUR", "quote": "GBP", "rate": 0.8931},
    },
    "gbp-jpy": {
        "2026-01-15": {"base": "GBP", "quote": "JPY", "rate": 196.51},
        "2026-06-01": {"base": "GBP", "quote": "JPY", "rate": 199.74},
        "2026-08-01": {"base": "GBP", "quote": "JPY", "rate": 190.87},
    },
    "eur-usd": {
        "2026-01-15": {"base": "EUR", "quote": "USD", "rate": 1.0829},
        "2026-06-01": {"base": "EUR", "quote": "USD", "rate": 1.1348},
        "2026-08-01": {"base": "EUR", "quote": "USD", "rate": 1.1567},
    },
}


def rate_for(pair: str, as_of: str) -> RateRecord | None:
    """Return the pinned rate for ``pair`` on ``as_of``, or ``None`` if unavailable."""
    by_date = _DATASET.get(pair)
    if by_date is None:
        return None
    return by_date.get(as_of)
