"""Offline lat/lon → IANA timezone lookup (no geocoding API)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# Named allowlisted place fixtures — not arbitrary geocoding (#107 / secretary-enrich-v1).
PLACES: Final = {
    "new-york": {
        "latitude": 40.7128,
        "longitude": -74.0060,
        "timezone": "America/New_York",
    },
    "london": {
        "latitude": 51.5074,
        "longitude": -0.1278,
        "timezone": "Europe/London",
    },
    "tokyo": {
        "latitude": 35.6762,
        "longitude": 139.6503,
        "timezone": "Asia/Tokyo",
    },
    "los-angeles": {
        "latitude": 34.0522,
        "longitude": -118.2437,
        "timezone": "America/Los_Angeles",
    },
    "sydney": {
        "latitude": -33.8688,
        "longitude": 151.2093,
        "timezone": "Australia/Sydney",
    },
    "chicago": {
        "latitude": 41.8781,
        "longitude": -87.6298,
        "timezone": "America/Chicago",
    },
    "paris": {
        "latitude": 48.8566,
        "longitude": 2.3522,
        "timezone": "Europe/Paris",
    },
}


@dataclass(frozen=True, slots=True)
class _Region:
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float
    timezone: str

    def contains(self, latitude: float, longitude: float) -> bool:
        return (
            self.min_lat <= latitude <= self.max_lat
            and self.min_lon <= longitude <= self.max_lon
        )


# Coarse offline regions — specific boxes before broad fallbacks (first match wins).
_REGIONS: tuple[_Region, ...] = (
    _Region(32.0, 49.5, -125.0, -114.0, "America/Los_Angeles"),
    _Region(31.0, 49.0, -114.0, -102.0, "America/Denver"),
    _Region(25.0, 49.0, -102.0, -87.0, "America/Chicago"),
    _Region(24.0, 49.5, -87.0, -66.0, "America/New_York"),
    _Region(49.0, 60.0, -141.0, -52.0, "America/Toronto"),
    _Region(51.0, 72.0, -170.0, -130.0, "America/Anchorage"),
    _Region(18.0, 23.0, -161.0, -154.0, "Pacific/Honolulu"),
    _Region(50.0, 60.0, -10.0, 2.0, "Europe/London"),
    _Region(41.0, 51.0, -5.0, 10.0, "Europe/Paris"),
    _Region(36.0, 47.0, 6.0, 19.0, "Europe/Rome"),
    _Region(55.0, 70.0, 20.0, 40.0, "Europe/Moscow"),
    _Region(30.0, 46.0, 129.0, 146.0, "Asia/Tokyo"),
    _Region(20.0, 40.0, 100.0, 122.0, "Asia/Shanghai"),
    _Region(8.0, 23.0, 68.0, 90.0, "Asia/Kolkata"),
    _Region(19.0, 33.0, 34.0, 56.0, "Asia/Dubai"),
    _Region(-45.0, -10.0, 112.0, 154.0, "Australia/Sydney"),
    _Region(-35.0, -22.0, 16.0, 33.0, "Africa/Johannesburg"),
    _Region(4.0, 14.0, -18.0, -8.0, "Africa/Abidjan"),
    _Region(-56.0, -17.0, -75.0, -53.0, "America/Santiago"),
    _Region(-35.0, 5.0, -82.0, -34.0, "America/Sao_Paulo"),
    _Region(14.0, 33.0, -118.0, -86.0, "America/Mexico_City"),
)


def timezone_at(latitude: float, longitude: float) -> str | None:
    """Return an IANA timezone for coordinates, or ``None`` when unresolved."""
    if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
        return None
    for region in _REGIONS:
        if region.contains(latitude, longitude):
            return region.timezone
    return None
