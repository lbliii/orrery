"""Named allowlisted venue fixtures — not open-ended place search (#109)."""

from __future__ import annotations

from typing import Final

_WEEKDAY_HOURS = {
    "monday": {"open": "09:00", "close": "21:00"},
    "tuesday": {"open": "09:00", "close": "21:00"},
    "wednesday": {"open": "09:00", "close": "21:00"},
    "thursday": {"open": "09:00", "close": "21:00"},
    "friday": {"open": "09:00", "close": "22:00"},
    "saturday": {"open": "10:00", "close": "22:00"},
    "sunday": {"open": "10:00", "close": "20:00"},
}

VENUES: Final = {
    "central-park-cafe-nyc": {
        "display_name": "Central Park Cafe (New York)",
        "timezone": "America/New_York",
        "hours": dict(_WEEKDAY_HOURS),
    },
    "british-museum-london": {
        "display_name": "British Museum Cafe (London)",
        "timezone": "Europe/London",
        "hours": {
            **_WEEKDAY_HOURS,
            "monday": {"closed": True},
        },
    },
    "tokyo-ramen-yokocho": {
        "display_name": "Ramen Yokocho (Tokyo)",
        "timezone": "Asia/Tokyo",
        "hours": {
            **_WEEKDAY_HOURS,
            "sunday": {"open": "11:00", "close": "23:00"},
        },
    },
    "griffith-cafe-la": {
        "display_name": "Griffith Observatory Cafe (Los Angeles)",
        "timezone": "America/Los_Angeles",
        "hours": dict(_WEEKDAY_HOURS),
    },
    "opera-bar-sydney": {
        "display_name": "Opera Bar (Sydney)",
        "timezone": "Australia/Sydney",
        "hours": {
            **_WEEKDAY_HOURS,
            "monday": {"open": "12:00", "close": "23:00"},
        },
    },
    "art-institute-cafe-chicago": {
        "display_name": "Art Institute Cafe (Chicago)",
        "timezone": "America/Chicago",
        "hours": dict(_WEEKDAY_HOURS),
    },
    "louvre-cafe-paris": {
        "display_name": "Louvre Cafe (Paris)",
        "timezone": "Europe/Paris",
        "hours": {
            **_WEEKDAY_HOURS,
            "tuesday": {"closed": True},
        },
    },
}
