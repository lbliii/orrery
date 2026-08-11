"""Offline timezone resolution — allowlisted places or lat/lon lookup."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .contract import DEFAULT_PLACE
from .lookup import PLACES, timezone_at


def resolve(
    *,
    place: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    """Resolve coordinates or a named place fixture to an IANA timezone."""
    observed_at = (clock or (lambda: datetime.now(UTC)))().isoformat()
    has_place = place is not None and str(place).strip() != ""
    has_lat = latitude is not None
    has_lon = longitude is not None

    if has_place:
        record = PLACES.get(str(place).strip())
        if record is None:
            return {
                "error": "place_not_allowed",
                "place": place,
                "live_at_call": True,
            }
        timezone = str(record["timezone"])
        resolved_lat = float(record["latitude"])
        resolved_lon = float(record["longitude"])
        source = f"place:{place}"
    elif has_lat or has_lon:
        if not (has_lat and has_lon):
            return {
                "error": "incomplete_coordinates",
                "latitude": latitude,
                "longitude": longitude,
                "live_at_call": True,
            }
        resolved_lat = float(latitude)  # type: ignore[arg-type]
        resolved_lon = float(longitude)  # type: ignore[arg-type]
        timezone = timezone_at(resolved_lat, resolved_lon)
        if timezone is None:
            return {
                "error": "coordinates_not_resolved",
                "latitude": resolved_lat,
                "longitude": resolved_lon,
                "live_at_call": True,
            }
        source = "latlon:offline"
    else:
        return {"error": "missing_input", "live_at_call": True}

    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        return {
            "error": "timezone_invalid",
            "timezone": timezone,
            "live_at_call": True,
        }

    return {
        "timezone": timezone,
        "latitude": resolved_lat,
        "longitude": resolved_lon,
        "source": source,
        "observed_at": observed_at,
        "offline": True,
        "live_at_call": True,
    }


def answer(*, place: str = DEFAULT_PLACE) -> dict[str, object]:
    """Return a concise timezone answer with the full resolution payload."""
    resolved = resolve(place=place)
    if resolved.get("error"):
        return resolved
    timezone = str(resolved["timezone"])
    label = place if place in PLACES else "coordinates"
    return {**resolved, "answer": f"{label} is in {timezone}"}
