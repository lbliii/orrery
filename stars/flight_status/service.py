"""Offline allowlisted flight id + date → schedule/status fields."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from .contract import DEFAULT_DATE, DEFAULT_FLIGHT
from .flights import FLIGHT_IDS, PINNED_DATES, SCHEDULE

PROVIDER = "orrery-fixtures"


def status(
    *,
    flight: str,
    date: str,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    """Resolve a named flight fixture and pinned date to status fields."""
    observed_at = (clock or (lambda: datetime.now(UTC)))().isoformat()
    flight_id = str(flight).strip().upper()
    date_str = str(date).strip()
    if not flight_id or not date_str:
        return {"error": "missing_input", "live_at_call": True}
    if flight_id not in FLIGHT_IDS:
        return {
            "error": "flight_not_allowed",
            "flight": flight,
            "live_at_call": True,
        }
    if date_str not in PINNED_DATES:
        return {
            "error": "date_not_available",
            "flight": flight_id,
            "date": date_str,
            "pinned_dates": list(PINNED_DATES),
            "live_at_call": True,
        }
    record = SCHEDULE.get((flight_id, date_str))
    if record is None:
        return {
            "error": "schedule_not_found",
            "flight": flight_id,
            "date": date_str,
            "live_at_call": True,
        }
    payload: dict[str, object] = {
        "flight": flight_id,
        "date": date_str,
        "status": str(record["status"]),
        "departure_airport": str(record["departure_airport"]),
        "arrival_airport": str(record["arrival_airport"]),
        "scheduled_departure": str(record["scheduled_departure"]),
        "scheduled_arrival": str(record["scheduled_arrival"]),
        "carrier": str(record["carrier"]),
        "provider": PROVIDER,
        "source": f"flight:{flight_id}:{date_str}",
        "observed_at": observed_at,
        "offline": True,
        "live_at_call": True,
    }
    if "actual_departure" in record:
        payload["actual_departure"] = str(record["actual_departure"])
    if "actual_arrival" in record:
        payload["actual_arrival"] = str(record["actual_arrival"])
    if "delay_minutes" in record:
        payload["delay_minutes"] = int(record["delay_minutes"])
    return payload


def answer(*, flight: str = DEFAULT_FLIGHT, date: str = DEFAULT_DATE) -> dict[str, object]:
    """Return a concise flight status answer with the full resolution payload."""
    resolved = status(flight=flight, date=date)
    if resolved.get("error"):
        return resolved
    flight_id = str(resolved["flight"])
    status_label = str(resolved["status"])
    departure = str(resolved["departure_airport"])
    arrival = str(resolved["arrival_airport"])
    return {
        **resolved,
        "answer": f"{flight_id} {departure}→{arrival} is {status_label}",
    }
