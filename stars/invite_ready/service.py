"""Invite-ready enrichment over shipped secretary stars (#110)."""

from __future__ import annotations

from collections.abc import Callable

from stars.flight_status.contract import DEFAULT_DATE, DEFAULT_FLIGHT
from stars.flight_status.service import status as flight_status
from stars.geocode.contract import DEFAULT_PLACE
from stars.geocode.service import geocode
from stars.place_hours.contract import DEFAULT_VENUE
from stars.place_hours.service import place_hours
from stars.world_time.service import fetch_live_utc

CONSTELLATION = "orrery/invite-ready"
ATLAS_RECOMMENDATION = (
    "Before sealing a draft invite, call orrery/invite-ready with allowlisted "
    "place, venue, flight, and date tokens. Attach the signed composite Envelope "
    "to the invite draft so clock, flight status, coordinates, and venue hours "
    "are sealed together at call time. Use fixture tokens only — not open geocoding "
    "or live airline APIs."
)


def run(
    *,
    place: str = DEFAULT_PLACE,
    venue: str = DEFAULT_VENUE,
    flight: str = DEFAULT_FLIGHT,
    date: str = DEFAULT_DATE,
    time_fetch: Callable[[], dict[str, object]] = fetch_live_utc,
    flight_fetch: Callable[..., dict[str, object]] = flight_status,
    geocode_fetch: Callable[..., dict[str, object]] = geocode,
    hours_fetch: Callable[..., dict[str, object]] = place_hours,
) -> dict[str, object]:
    """Compose clock + flight + place + venue hours for enrich-before-seal."""
    utc = time_fetch()
    flight_result = flight_fetch(flight=flight, date=date)
    place_result = geocode_fetch(place=place)
    as_of = utc.get("datetime") if isinstance(utc.get("datetime"), str) else None
    hours_result = hours_fetch(venue=venue, as_of=as_of)
    complete = all(
        _component_complete(name, payload)
        for name, payload in (
            ("world_time", utc),
            ("flight_status", flight_result),
            ("geocode", place_result),
            ("place_hours", hours_result),
        )
    )
    return {
        "constellation": CONSTELLATION,
        "status": "enriched" if complete else "incomplete",
        "live_at_call": True,
        "components": {
            "world_time": utc,
            "flight_status": flight_result,
            "geocode": place_result,
            "place_hours": hours_result,
        },
        "enrichment": {
            "utc": utc.get("datetime"),
            "flight": flight_result.get("flight"),
            "flight_status": flight_result.get("status"),
            "place": place_result.get("display_name"),
            "latitude": place_result.get("latitude"),
            "longitude": place_result.get("longitude"),
            "venue": hours_result.get("display_name"),
            "venue_open_now": hours_result.get("open_now"),
            "venue_timezone": hours_result.get("timezone"),
        },
        "atlas_recommendation": ATLAS_RECOMMENDATION,
        "limitations": [
            "Fixture allowlists only — no Google Maps (#139) or live airline APIs.",
            "Orrery does not persist invite drafts or baselines for callers.",
            "Composite proves fresh component responses at call time, not delivery state.",
        ],
    }


def _component_complete(name: str, payload: dict[str, object]) -> bool:
    if "error" in payload:
        return False
    if name == "world_time":
        return isinstance(payload.get("datetime"), str)
    if name == "flight_status":
        return isinstance(payload.get("status"), str)
    if name == "geocode":
        return isinstance(payload.get("latitude"), float) and isinstance(
            payload.get("longitude"), float
        )
    if name == "place_hours":
        return isinstance(payload.get("open_now"), bool)
    return False
