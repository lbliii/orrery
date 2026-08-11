"""Deterministic fixtures for the geocode Star."""

from __future__ import annotations

from .places import PLACES

DEFAULT_PLACE = "new-york"
DEFAULT_DISPLAY_NAME = str(PLACES[DEFAULT_PLACE]["display_name"])
DEFAULT_LATITUDE = float(PLACES[DEFAULT_PLACE]["latitude"])
DEFAULT_LONGITUDE = float(PLACES[DEFAULT_PLACE]["longitude"])
