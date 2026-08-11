"""Static public-holiday lookup — allowlisted region codes and pinned years."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from .contract import DEFAULT_REGION, DEFAULT_YEAR
from .dataset import PINNED_YEARS, REGIONS, holidays_for

SOURCE = "static:orrery/holidays-v1"


def list_holidays(
    *,
    region: str = DEFAULT_REGION,
    year: int = DEFAULT_YEAR,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    """Return the pinned holiday list for an allowlisted region and year."""
    observed_at = (clock or (lambda: datetime.now(UTC)))().isoformat()
    code = str(region).strip().upper()
    if code not in REGIONS:
        return {
            "error": "region_not_allowed",
            "region": region,
            "live_at_call": True,
        }
    if year not in PINNED_YEARS:
        return {
            "error": "year_not_available",
            "region": code,
            "year": year,
            "pinned_years": sorted(PINNED_YEARS),
            "live_at_call": True,
        }
    records = holidays_for(code, year)
    if records is None:
        return {
            "error": "year_not_available",
            "region": code,
            "year": year,
            "pinned_years": sorted(PINNED_YEARS),
            "live_at_call": True,
        }
    holidays = [dict(item) for item in records]
    return {
        "region": code,
        "year": year,
        "holidays": holidays,
        "count": len(holidays),
        "source": SOURCE,
        "observed_at": observed_at,
        "offline": True,
        "live_at_call": True,
    }


def answer(*, region: str = DEFAULT_REGION, year: int = DEFAULT_YEAR) -> dict[str, object]:
    """Return a concise holiday summary with the full list payload."""
    listed = list_holidays(region=region, year=year)
    if listed.get("error"):
        return listed
    count = int(listed["count"])
    code = str(listed["region"])
    yr = int(listed["year"])
    return {
        **listed,
        "answer": f"{code} has {count} public holidays in {yr}",
    }
