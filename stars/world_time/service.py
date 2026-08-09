"""Framework-free World Time service, preserving the dogfood call behavior."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from .contract import CLONE_WARNING, WORLD_TIME_URL


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
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return {
            "error": "upstream_unreachable",
            "detail": str(exc),
            "timezone": "UTC",
            "source": WORLD_TIME_URL,
            "live_at_call": True,
            "clone_warning": CLONE_WARNING,
        }
    if not isinstance(raw, dict):
        return {
            "error": "upstream_malformed",
            "timezone": "UTC",
            "source": WORLD_TIME_URL,
            "live_at_call": True,
            "clone_warning": CLONE_WARNING,
        }
    return _payload(raw, source=WORLD_TIME_URL)


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
