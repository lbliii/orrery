"""Deterministic fixtures for the timezone resolution Star."""

from __future__ import annotations

from .lookup import PLACES

DEFAULT_PLACE = "new-york"
DEFAULT_TIMEZONE = str(PLACES[DEFAULT_PLACE]["timezone"])
TOKYO_LATLON = {"latitude": 35.6762, "longitude": 139.6503}
TOKYO_TIMEZONE = "Asia/Tokyo"
