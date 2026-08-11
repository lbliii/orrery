"""Tests for orrery/geocode — offline allowlisted place geocoding (#106)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from dogfood import verify_receipt as verify_envelope_wire
from stars.builtins import builtin_registry
from stars.geocode.contract import tool_schemas
from stars.geocode.corpus import CORPUS
from stars.geocode.fixtures import (
    DEFAULT_DISPLAY_NAME,
    DEFAULT_LATITUDE,
    DEFAULT_LONGITUDE,
    DEFAULT_PLACE,
)
from stars.geocode.places import PLACES
from stars.geocode.service import answer, geocode
from stars.geocode.skill import build_skill
from tests.stars.helpers import (
    assert_allowlist_rejects,
    assert_manifest_publish_corpus,
    assert_payload_keys,
    assert_tool_schema_keys,
    load_star_manifest,
)

FIXED_TIME = datetime(2026, 8, 11, 12, 0, 0, tzinfo=UTC)


@pytest.mark.issue(106)
class TestGeocodeHappyPath:
    def test_allowlisted_place_returns_coordinates_and_display_name(self) -> None:
        result = geocode(place="new-york", clock=lambda: FIXED_TIME)
        assert result == {
            "place": "new-york",
            "display_name": "New York, NY",
            "latitude": PLACES["new-york"]["latitude"],
            "longitude": PLACES["new-york"]["longitude"],
            "provider": "orrery-fixtures",
            "source": "place:new-york",
            "observed_at": FIXED_TIME.isoformat(),
            "offline": True,
            "live_at_call": True,
        }

    def test_answer_wraps_place_geocode(self) -> None:
        result = answer(place=DEFAULT_PLACE)
        assert result["display_name"] == DEFAULT_DISPLAY_NAME
        assert result["latitude"] == DEFAULT_LATITUDE
        assert result["longitude"] == DEFAULT_LONGITUDE
        assert result["answer"] == (
            f"{DEFAULT_DISPLAY_NAME} is at {DEFAULT_LATITUDE}, {DEFAULT_LONGITUDE}"
        )


@pytest.mark.issue(106)
class TestGeocodeAllowlistNegative:
    def test_out_of_allowlist_place_fails_loud(self) -> None:
        result = assert_allowlist_rejects(
            geocode,
            place="unknown-city",
            error="place_not_allowed",
            clock=lambda: FIXED_TIME,
        )
        assert result["live_at_call"] is True


@pytest.mark.issue(106)
class TestGeocodeContractAndEnvelope:
    def test_corpus_non_empty(self) -> None:
        assert len(CORPUS) >= 2

    def test_manifest_offline_policy_and_publish_corpus(self) -> None:
        manifest = load_star_manifest("geocode")
        assert manifest["policy"]["allowed_egress"] == []
        assert_tool_schema_keys(tool_schemas(), {"geocode", "answer"})
        assert_manifest_publish_corpus("geocode")

    def test_skill_envelope_is_sealable(self) -> None:
        skill = build_skill()
        assert {tool.name for tool in skill._pending} == {"geocode", "answer"}
        envelope = next(tool for tool in skill._pending if tool.name == "answer").handler(
            place="london"
        )
        wire = envelope.to_wire()
        assert wire["payload"]["display_name"] == "London, UK"
        assert verify_envelope_wire(wire, skill=skill) is True

    def test_registry_discovers_direct_endpoint(self) -> None:
        definition = next(item for item in builtin_registry() if item.name == "orrery/geocode")
        assert definition.direct_mcp_path == "/stars/geocode/mcp"

    def test_payload_keys_on_happy_path(self) -> None:
        assert_payload_keys(
            geocode(place="paris", clock=lambda: FIXED_TIME),
            (
                "place",
                "display_name",
                "latitude",
                "longitude",
                "provider",
                "offline",
                "live_at_call",
            ),
        )
