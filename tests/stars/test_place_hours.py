"""Tests for orrery/place-hours — offline allowlisted venue hours (#109)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from dogfood import verify_receipt as verify_envelope_wire
from stars.builtins import builtin_registry
from stars.place_hours.contract import tool_schemas
from stars.place_hours.corpus import CORPUS
from stars.place_hours.fixtures import DEFAULT_DISPLAY_NAME, DEFAULT_VENUE
from stars.place_hours.service import answer, place_hours
from stars.place_hours.skill import build_skill
from stars.place_hours.venues import VENUES
from tests.stars.helpers import (
    assert_allowlist_rejects,
    assert_manifest_publish_corpus,
    assert_payload_keys,
    assert_tool_schema_keys,
    load_star_manifest,
)

FIXED_TIME = datetime(2026, 8, 11, 14, 0, 0, tzinfo=UTC)


@pytest.mark.issue(109)
class TestPlaceHoursHappyPath:
    def test_allowlisted_venue_returns_hours_and_open_now(self) -> None:
        result = place_hours(
            venue="central-park-cafe-nyc",
            clock=lambda: FIXED_TIME,
        )
        assert result["venue"] == "central-park-cafe-nyc"
        assert result["display_name"] == VENUES["central-park-cafe-nyc"]["display_name"]
        assert result["timezone"] == "America/New_York"
        assert result["open_now"] is True
        assert result["weekday"] == "tuesday"
        assert result["provider"] == "orrery-fixtures"
        assert result["offline"] is True
        assert "monday" in result["hours"]

    def test_as_of_overrides_clock_for_open_now(self) -> None:
        closed_moment = "2026-08-11T03:00:00+00:00"
        result = place_hours(
            venue="central-park-cafe-nyc",
            as_of=closed_moment,
            clock=lambda: FIXED_TIME,
        )
        assert result["as_of"] == "2026-08-11T03:00:00+00:00"
        assert result["open_now"] is False

    def test_answer_wraps_venue_hours(self) -> None:
        result = answer(venue=DEFAULT_VENUE, clock=lambda: FIXED_TIME)
        assert result["display_name"] == DEFAULT_DISPLAY_NAME
        assert result["open_now"] is True
        assert "Central Park Cafe" in str(result["answer"])
        assert "open" in str(result["answer"])


@pytest.mark.issue(109)
class TestPlaceHoursAllowlistNegative:
    def test_out_of_allowlist_venue_fails_loud(self) -> None:
        result = assert_allowlist_rejects(
            place_hours,
            venue="unknown-cafe",
            error="venue_not_allowed",
            clock=lambda: FIXED_TIME,
        )
        assert result["live_at_call"] is True


@pytest.mark.issue(109)
class TestPlaceHoursContractAndEnvelope:
    def test_corpus_non_empty(self) -> None:
        assert len(CORPUS) >= 2

    def test_manifest_offline_policy_and_publish_corpus(self) -> None:
        manifest = load_star_manifest("place_hours")
        assert manifest["policy"]["allowed_egress"] == []
        assert_tool_schema_keys(tool_schemas(), {"place_hours", "answer"})
        assert_manifest_publish_corpus("place_hours")

    def test_skill_envelope_is_sealable(self) -> None:
        skill = build_skill()
        assert {tool.name for tool in skill._pending} == {"place_hours", "answer"}
        envelope = next(tool for tool in skill._pending if tool.name == "answer").handler(
            venue="louvre-cafe-paris",
        )
        wire = envelope.to_wire()
        assert wire["payload"]["venue"] == "louvre-cafe-paris"
        assert verify_envelope_wire(wire, skill=skill) is True

    def test_registry_discovers_direct_endpoint(self) -> None:
        definition = next(
            item for item in builtin_registry() if item.name == "orrery/place-hours"
        )
        assert definition.direct_mcp_path == "/stars/place-hours/mcp"

    def test_payload_keys_on_happy_path(self) -> None:
        assert_payload_keys(
            place_hours(venue="tokyo-ramen-yokocho", clock=lambda: FIXED_TIME),
            (
                "venue",
                "display_name",
                "timezone",
                "hours",
                "open_now",
                "provider",
                "offline",
                "live_at_call",
            ),
        )
