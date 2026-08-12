"""Deterministic fixtures for the FX rate Star."""

from __future__ import annotations

from .rates import rate_for

DEFAULT_PAIR = "usd-eur"
DEFAULT_AS_OF = "2026-06-01"
_DEFAULT = rate_for(DEFAULT_PAIR, DEFAULT_AS_OF)
assert _DEFAULT is not None
DEFAULT_BASE = _DEFAULT["base"]
DEFAULT_QUOTE = _DEFAULT["quote"]
DEFAULT_RATE = _DEFAULT["rate"]
