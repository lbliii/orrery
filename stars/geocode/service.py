"""Offline allowlisted place token → coordinates + display name."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from .contract import DEFAULT_PLACE
from .places import PLACES

PROVIDER = "orrery-fixtures"


def geocode(
    *,
    place: str,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    """Resolve a named place fixture to coordinates and a display name."""
    observed_at = (clock or (lambda: datetime.now(UTC)))().isoformat()
    token = str(place).strip()
    if not token:
        return {"error": "missing_input", "live_at_call": True}
    record = PLACES.get(token)
    if record is None:
        return {
            "error": "place_not_allowed",
            "place": place,
            "live_at_call": True,
        }
    return {
        "place": token,
        "display_name": str(record["display_name"]),
        "latitude": float(record["latitude"]),
        "longitude": float(record["longitude"]),
        "provider": PROVIDER,
        "source": f"place:{token}",
        "observed_at": observed_at,
        "offline": True,
        "live_at_call": True,
    }


def answer(*, place: str = DEFAULT_PLACE) -> dict[str, object]:
    """Return a concise geocode answer with the full resolution payload."""
    resolved = geocode(place=place)
    if resolved.get("error"):
        return resolved
    display_name = str(resolved["display_name"])
    latitude = resolved["latitude"]
    longitude = resolved["longitude"]
    return {
        **resolved,
        "answer": f"{display_name} is at {latitude}, {longitude}",
    }
