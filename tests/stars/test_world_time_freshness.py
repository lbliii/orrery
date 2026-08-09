"""Truthfulness tests for live clock-provider freshness and fallback behavior."""

from __future__ import annotations

from datetime import UTC, datetime

from stars.world_time.service import _is_fresh_utc


def test_clock_freshness_accepts_utc_naive_or_offset_values() -> None:
    now = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)

    assert _is_fresh_utc("2026-08-09T11:59:00", now=now)
    assert _is_fresh_utc("2026-08-09T12:01:00Z", now=now)
    assert not _is_fresh_utc("2026-08-09T11:50:00", now=now)
    assert not _is_fresh_utc("not a datetime", now=now)
