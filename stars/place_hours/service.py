"""Offline allowlisted venue token → hours / open-now."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from .contract import DEFAULT_VENUE
from .venues import VENUES

PROVIDER = "orrery-fixtures"
_WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


def _resolve_moment(
    *,
    as_of: str | None,
    clock: Callable[[], datetime],
) -> datetime:
    if as_of is None:
        return clock()
    token = str(as_of).strip()
    if not token:
        return clock()
    parsed = datetime.fromisoformat(token.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _parse_hhmm(value: str) -> time:
    hour, minute = value.split(":", 1)
    return time(int(hour), int(minute))


def _hours_for_day(day_hours: Mapping[str, object]) -> dict[str, object]:
    if day_hours.get("closed"):
        return {"closed": True}
    return {
        "open": str(day_hours["open"]),
        "close": str(day_hours["close"]),
    }


def _is_open_now(*, day_hours: Mapping[str, object], local_moment: datetime) -> bool:
    if day_hours.get("closed"):
        return False
    open_at = _parse_hhmm(str(day_hours["open"]))
    close_at = _parse_hhmm(str(day_hours["close"]))
    current = local_moment.time()
    return open_at <= current < close_at


def place_hours(
    *,
    venue: str,
    as_of: str | None = None,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    """Resolve a named venue fixture to weekly hours and open-now status."""
    observed_at = (clock or (lambda: datetime.now(UTC)))().isoformat()
    token = str(venue).strip()
    if not token:
        return {"error": "missing_input", "live_at_call": True}
    record = VENUES.get(token)
    if record is None:
        return {
            "error": "venue_not_allowed",
            "venue": venue,
            "live_at_call": True,
        }
    moment = _resolve_moment(as_of=as_of, clock=clock or (lambda: datetime.now(UTC)))
    timezone = str(record["timezone"])
    local_moment = moment.astimezone(ZoneInfo(timezone))
    weekday = _WEEKDAYS[local_moment.weekday()]
    raw_hours = record["hours"]
    weekly_hours = {
        day: _hours_for_day(raw_hours[day])  # type: ignore[index]
        for day in _WEEKDAYS
    }
    today_hours = weekly_hours[weekday]
    open_now = _is_open_now(day_hours=raw_hours[weekday], local_moment=local_moment)  # type: ignore[index]
    return {
        "venue": token,
        "display_name": str(record["display_name"]),
        "timezone": timezone,
        "hours": weekly_hours,
        "weekday": weekday,
        "today_hours": today_hours,
        "open_now": open_now,
        "as_of": moment.isoformat(),
        "provider": PROVIDER,
        "source": f"venue:{token}",
        "observed_at": observed_at,
        "offline": True,
        "live_at_call": True,
    }


def answer(
    *,
    venue: str = DEFAULT_VENUE,
    as_of: str | None = None,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    """Return a concise venue-hours answer with the full resolution payload."""
    resolved = place_hours(venue=venue, as_of=as_of, clock=clock)
    if resolved.get("error"):
        return resolved
    display_name = str(resolved["display_name"])
    status = "open" if resolved["open_now"] else "closed"
    today_hours = resolved["today_hours"]
    if today_hours.get("closed"):
        hours_text = "closed today"
    else:
        hours_text = f"open {today_hours['open']}-{today_hours['close']} today"
    return {
        **resolved,
        "answer": f"{display_name} is {status} now ({hours_text})",
    }
