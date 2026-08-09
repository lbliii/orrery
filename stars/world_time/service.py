"""Framework-free World Time service, preserving the dogfood call behavior."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

from .contract import CLONE_WARNING, FALLBACK_TIME_URL, WORLD_TIME_URL

MAX_UPSTREAM_SKEW_SECONDS = 300


def _payload(raw: dict[str, Any], *, source: str) -> dict[str, object]:
    datetime_s = raw.get("dateTime") or raw.get("datetime") or raw.get("utc_datetime")
    return {
        "timezone": str(raw.get("timeZone") or raw.get("timezone") or "UTC"),
        "datetime": datetime_s,
        "date": raw.get("date"),
        "time": raw.get("time"),
        "day_of_week": raw.get("dayOfWeek") or raw.get("day_of_week"),
        "source": source,
        "live_at_call": True,
        "clone_warning": CLONE_WARNING,
    }


def _is_fresh_utc(value: object, *, now: datetime | None = None) -> bool:
    """Return whether an upstream UTC instant is sufficiently recent to claim live truth."""
    if not isinstance(value, str):
        return False
    try:
        observed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=UTC)
    current = now or datetime.now(UTC)
    return abs((current - observed).total_seconds()) <= MAX_UPSTREAM_SKEW_SECONDS


def _fallback_google_date() -> dict[str, Any]:
    """Use a no-store HTTP Date header only when the primary clock is stale/unavailable."""
    request = urllib.request.Request(
        FALLBACK_TIME_URL,
        headers={
            "User-Agent": "orrery-world-time/0.1 (+https://github.com/lbliii/orrery)",
            "Cache-Control": "no-cache",
        },
        method="HEAD",
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        header = response.headers.get("Date")
    if not header:
        raise ValueError("fallback clock response has no Date header")
    observed = parsedate_to_datetime(header).astimezone(UTC)
    return {
        "dateTime": observed.isoformat().replace("+00:00", "Z"),
        "timeZone": "UTC",
    }


def fetch_live_utc() -> dict[str, object]:
    """Pull a live UTC reading, with an environment fixture for deterministic tests."""
    override = os.environ.get("ORRERY_WORLD_TIME_JSON", "").strip()
    if override:
        raw = json.loads(override)
        if not isinstance(raw, dict):
            raise ValueError("ORRERY_WORLD_TIME_JSON must be a JSON object")
        return _payload(raw, source="fixture:ORRERY_WORLD_TIME_JSON")

    request = urllib.request.Request(
        WORLD_TIME_URL,
        headers={
            "User-Agent": "orrery-world-time/0.1 (+https://github.com/lbliii/orrery)",
            "Accept": "application/json",
        },
    )
    primary_error = ""
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        primary_error = f"primary unavailable: {exc}"
    else:
        if isinstance(raw, dict) and _is_fresh_utc(raw.get("dateTime")):
            return _payload(raw, source=WORLD_TIME_URL)
        primary_error = "primary returned malformed or stale UTC observation"

    try:
        fallback = _fallback_google_date()
        if _is_fresh_utc(fallback.get("dateTime")):
            return _payload(fallback, source=FALLBACK_TIME_URL)
        raise ValueError("fallback returned stale UTC observation")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return {
            "error": "upstream_unreachable",
            "detail": f"{primary_error}; fallback unavailable: {exc}",
            "timezone": "UTC",
            "source": WORLD_TIME_URL,
            "live_at_call": True,
            "clone_warning": CLONE_WARNING,
        }


def fetch() -> dict[str, object]:
    """Fetch a fresh UTC reading through the canonical tool service name."""
    return fetch_live_utc()


def get() -> dict[str, object]:
    """Get the same fresh live reading exposed by :func:`fetch`."""
    return fetch_live_utc()


def answer() -> dict[str, object]:
    """Return a concise UTC answer with the complete fresh evidence payload."""
    live = fetch_live_utc()
    when = live.get("datetime") or live.get("error") or "unknown"
    return {**live, "answer": f"UTC now is {when}"}
