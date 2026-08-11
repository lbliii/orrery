"""Deterministic fixtures for the flight-status Star."""

from __future__ import annotations

from .contract import DEFAULT_DATE, DEFAULT_FLIGHT
from .flights import SCHEDULE

DEFAULT_STATUS = str(SCHEDULE[(DEFAULT_FLIGHT, DEFAULT_DATE)]["status"])
DEFAULT_DEPARTURE = str(SCHEDULE[(DEFAULT_FLIGHT, DEFAULT_DATE)]["departure_airport"])
DEFAULT_ARRIVAL = str(SCHEDULE[(DEFAULT_FLIGHT, DEFAULT_DATE)]["arrival_airport"])
