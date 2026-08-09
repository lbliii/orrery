"""Deterministic fixtures for the World Time Star."""

from __future__ import annotations

import json

UTC_FIXTURE = {
    "timeZone": "UTC",
    "dateTime": "2026-08-08T12:34:56Z",
    "date": "2026-08-08",
    "time": "12:34:56",
    "dayOfWeek": "Saturday",
}


def fixture_environment(payload: dict[str, object] | None = None) -> dict[str, str]:
    """Return the environment mapping consumed by :mod:`.service`."""
    return {"ORRERY_WORLD_TIME_JSON": json.dumps(payload or UTC_FIXTURE)}
