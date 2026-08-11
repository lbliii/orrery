"""Named allowlisted flight schedule/status fixtures — no live airline egress (#105)."""

from __future__ import annotations

from typing import Final

# Composite key: (flight_id, date) → status record.
SCHEDULE: Final = {
    ("AA100", "2026-08-11"): {
        "status": "on_time",
        "departure_airport": "JFK",
        "arrival_airport": "LAX",
        "scheduled_departure": "08:00",
        "scheduled_arrival": "11:30",
        "carrier": "American Airlines",
    },
    ("AA100", "2026-08-12"): {
        "status": "delayed",
        "departure_airport": "JFK",
        "arrival_airport": "LAX",
        "scheduled_departure": "08:00",
        "scheduled_arrival": "11:30",
        "actual_departure": "08:45",
        "delay_minutes": 45,
        "carrier": "American Airlines",
    },
    ("UA456", "2026-08-11"): {
        "status": "landed",
        "departure_airport": "SFO",
        "arrival_airport": "ORD",
        "scheduled_departure": "06:15",
        "scheduled_arrival": "12:20",
        "actual_departure": "06:10",
        "actual_arrival": "12:05",
        "carrier": "United Airlines",
    },
    ("DL789", "2026-08-11"): {
        "status": "cancelled",
        "departure_airport": "ATL",
        "arrival_airport": "SEA",
        "scheduled_departure": "14:00",
        "scheduled_arrival": "16:45",
        "carrier": "Delta Air Lines",
    },
    ("BA178", "2026-08-11"): {
        "status": "scheduled",
        "departure_airport": "LHR",
        "arrival_airport": "JFK",
        "scheduled_departure": "10:30",
        "scheduled_arrival": "13:15",
        "carrier": "British Airways",
    },
}

FLIGHT_IDS: Final = sorted({flight for flight, _date in SCHEDULE})
PINNED_DATES: Final = sorted({date for _flight, date in SCHEDULE})
