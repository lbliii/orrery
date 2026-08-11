"""Tests for orrery/tz-resolve — offline timezone resolution (#107)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from dogfood import verify_receipt as verify_envelope_wire
from stars.builtins import builtin_registry
from stars.tz_resolve.contract import tool_schemas
from stars.tz_resolve.corpus import CORPUS
from stars.tz_resolve.fixtures import DEFAULT_PLACE, DEFAULT_TIMEZONE, TOKYO_LATLON, TOKYO_TIMEZONE
from stars.tz_resolve.lookup import PLACES, timezone_at
from stars.tz_resolve.service import answer, resolve
from stars.tz_resolve.skill import build_skill
from tests.stars.helpers import (
    assert_allowlist_rejects,
    assert_manifest_publish_corpus,
    assert_payload_keys,
    assert_tool_schema_keys,
    load_star_manifest,
)

FIXED_TIME = datetime(2026, 8, 11, 12, 0, 0, tzinfo=UTC)


@pytest.mark.issue(107)
class TestTzResolveHappyPath:
    def test_place_token_resolves_to_iana_timezone(self) -> None:
        result = resolve(place="new-york", clock=lambda: FIXED_TIME)
        assert result == {
            "timezone": "America/New_York",
            "latitude": PLACES["new-york"]["latitude"],
            "longitude": PLACES["new-york"]["longitude"],
            "source": "place:new-york",
            "observed_at": FIXED_TIME.isoformat(),
            "offline": True,
            "live_at_call": True,
        }

    def test_latlon_resolves_offline(self) -> None:
        result = resolve(
            latitude=TOKYO_LATLON["latitude"],
            longitude=TOKYO_LATLON["longitude"],
            clock=lambda: FIXED_TIME,
        )
        assert result["timezone"] == TOKYO_TIMEZONE
        assert result["source"] == "latlon:offline"
        assert result["offline"] is True

    def test_answer_wraps_place_resolution(self) -> None:
        result = answer(place=DEFAULT_PLACE)
        assert result["timezone"] == DEFAULT_TIMEZONE
        assert result["answer"] == f"{DEFAULT_PLACE} is in {DEFAULT_TIMEZONE}"


@pytest.mark.issue(107)
class TestTzResolveAllowlistNegative:
    def test_out_of_allowlist_place_fails_loud(self) -> None:
        result = assert_allowlist_rejects(
            resolve,
            place="unknown-city",
            error="place_not_allowed",
            clock=lambda: FIXED_TIME,
        )
        assert result["live_at_call"] is True

    def test_unresolved_coordinates_fail_loud(self) -> None:
        result = resolve(latitude=0.0, longitude=0.0, clock=lambda: FIXED_TIME)
        assert result["error"] == "coordinates_not_resolved"
        assert result["live_at_call"] is True


@pytest.mark.issue(107)
class TestTzResolveContractAndEnvelope:
    def test_corpus_non_empty(self) -> None:
        assert len(CORPUS) >= 2

    def test_manifest_offline_policy_and_publish_corpus(self) -> None:
        manifest = load_star_manifest("tz_resolve")
        assert manifest["policy"]["allowed_egress"] == []
        assert_tool_schema_keys(tool_schemas(), {"resolve", "answer"})
        assert_manifest_publish_corpus("tz_resolve")

    def test_skill_envelope_is_sealable(self) -> None:
        skill = build_skill()
        assert {tool.name for tool in skill._pending} == {"resolve", "answer"}
        envelope = next(tool for tool in skill._pending if tool.name == "answer").handler(
            place="london"
        )
        wire = envelope.to_wire()
        assert wire["payload"]["timezone"] == "Europe/London"
        assert verify_envelope_wire(wire, skill=skill) is True

    def test_registry_discovers_direct_endpoint(self) -> None:
        definition = next(item for item in builtin_registry() if item.name == "orrery/tz-resolve")
        assert definition.direct_mcp_path == "/stars/tz-resolve/mcp"

    def test_lookup_helper_covers_major_cities(self) -> None:
        assert timezone_at(40.7128, -74.0060) == "America/New_York"
        assert timezone_at(51.5074, -0.1278) == "Europe/London"
        assert_payload_keys(
            resolve(place="paris", clock=lambda: FIXED_TIME),
            ("timezone", "latitude", "longitude", "source", "offline", "live_at_call"),
        )
