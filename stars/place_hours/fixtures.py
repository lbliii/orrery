"""Deterministic fixtures for the place-hours Star."""

from __future__ import annotations

from .venues import VENUES

DEFAULT_VENUE = "central-park-cafe-nyc"
DEFAULT_DISPLAY_NAME = str(VENUES[DEFAULT_VENUE]["display_name"])
DEFAULT_TIMEZONE = str(VENUES[DEFAULT_VENUE]["timezone"])
