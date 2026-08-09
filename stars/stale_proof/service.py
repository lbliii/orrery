"""Actual stale-proof composition over the two live evidence Stars."""

from __future__ import annotations

from collections.abc import Callable

from stars.source_watch.service import diff as source_diff
from stars.world_time.service import fetch_live_utc

SOURCE = "python-release-notes"


def run(
    source_digest: str = "",
    *,
    time_fetch: Callable[[], dict[str, object]] = fetch_live_utc,
    diff_fetch: Callable[[str, str], dict[str, object]] = source_diff,
) -> dict[str, object]:
    """Seal freshly fetched UTC and release-note digest evidence in one result.

    ``source_digest`` is deliberately caller-held.  Orrery only observes now;
    this constellation neither persists a baseline nor claims a deployment or
    PDF artifact was created.
    """
    utc = time_fetch()
    source = diff_fetch(SOURCE, source_digest)
    complete = _time_complete(utc) and _source_complete(source)
    return {
        "constellation": "orrery/stale-proof",
        "status": "fresh_proof" if complete else "incomplete",
        "live_at_call": True,
        "components": {
            "world_time": utc,
            "source_watch": source,
        },
        "utc": utc.get("datetime"),
        "source": SOURCE,
        "source_status": source.get("status") if "error" not in source else "unavailable",
        "known_source_digest": source.get("known_digest") or source_digest or None,
        "current_source_digest": source.get("current_digest"),
        "limitations": [
            "No caller baseline or source observation is persisted by Orrery.",
            "This receipt proves fresh component responses at call time, not a deployment state.",
            "Optional PDF rendering is a separate managed-artifact Star and is not invoked here.",
        ],
    }


def _time_complete(payload: dict[str, object]) -> bool:
    return "error" not in payload and isinstance(payload.get("datetime"), str)


def _source_complete(payload: dict[str, object]) -> bool:
    return "error" not in payload and isinstance(payload.get("current_digest"), str)
