"""Named allowlisted place fixtures — not arbitrary geocoding (#106)."""

from __future__ import annotations

from typing import Final

PLACES: Final = {
    "new-york": {
        "display_name": "New York, NY",
        "latitude": 40.7128,
        "longitude": -74.0060,
    },
    "london": {
        "display_name": "London, UK",
        "latitude": 51.5074,
        "longitude": -0.1278,
    },
    "tokyo": {
        "display_name": "Tokyo, Japan",
        "latitude": 35.6762,
        "longitude": 139.6503,
    },
    "los-angeles": {
        "display_name": "Los Angeles, CA",
        "latitude": 34.0522,
        "longitude": -118.2437,
    },
    "sydney": {
        "display_name": "Sydney, Australia",
        "latitude": -33.8688,
        "longitude": 151.2093,
    },
    "chicago": {
        "display_name": "Chicago, IL",
        "latitude": 41.8781,
        "longitude": -87.6298,
    },
    "paris": {
        "display_name": "Paris, France",
        "latitude": 48.8566,
        "longitude": 2.3522,
    },
}
