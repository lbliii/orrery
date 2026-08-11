"""Tests for orrery/holidays — static pinned public holiday lookup (#108)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from dogfood import verify_receipt as verify_envelope_wire
from stars.builtins import builtin_registry
from stars.holidays.contract import DEFAULT_REGION, DEFAULT_YEAR, tool_schemas
from stars.holidays.corpus import CORPUS
from stars.holidays.dataset import REGIONS
from stars.holidays.fixtures import DEFAULT_HOLIDAY_COUNT
from stars.holidays.service import answer, list_holidays
from stars.holidays.skill import build_skill
from tests.stars.helpers import (
    assert_allowlist_rejects,
    assert_manifest_publish_corpus,
    assert_payload_keys,
    assert_tool_schema_keys,
    load_star_manifest,
)

FIXED_TIME = datetime(2026, 8, 11, 12, 0, 0, tzinfo=UTC)


@pytest.mark.issue(108)
class TestHolidaysHappyPath:
    def test_allowlisted_region_returns_pinned_holidays(self) -> None:
        result = list_holidays(
            region=DEFAULT_REGION,
            year=DEFAULT_YEAR,
            clock=lambda: FIXED_TIME,
        )
        assert result["region"] == "US"
        assert result["year"] == DEFAULT_YEAR
        assert result["count"] == DEFAULT_HOLIDAY_COUNT
        assert result["offline"] is True
        holidays = result["holidays"]
        assert isinstance(holidays, list)
        assert holidays[0]["date"] == "2026-01-01"
        assert holidays[0]["name"] == "New Year's Day"

    def test_answer_wraps_holiday_list(self) -> None:
        result = answer(region="GB", year=2026)
        assert result["region"] == "GB"
        assert result["answer"] == "GB has 8 public holidays in 2026"
        assert "Christmas Day" in {item["name"] for item in result["holidays"]}


@pytest.mark.issue(108)
class TestHolidaysAllowlistNegative:
    def test_out_of_allowlist_region_fails_loud(self) -> None:
        result = assert_allowlist_rejects(
            list_holidays,
            region="ZZ",
            year=2026,
            error="region_not_allowed",
            clock=lambda: FIXED_TIME,
        )
        assert result["live_at_call"] is True

    def test_unpinned_year_fails_loud(self) -> None:
        result = list_holidays(region="US", year=1999, clock=lambda: FIXED_TIME)
        assert result["error"] == "year_not_available"
        assert result["live_at_call"] is True


@pytest.mark.issue(108)
class TestHolidaysContractAndEnvelope:
    def test_corpus_non_empty(self) -> None:
        assert len(CORPUS) >= 2

    def test_manifest_offline_policy_and_publish_corpus(self) -> None:
        manifest = load_star_manifest("holidays")
        assert manifest["policy"]["allowed_egress"] == []
        assert_tool_schema_keys(tool_schemas(), {"list", "answer"})
        assert_manifest_publish_corpus("holidays")

    def test_skill_envelope_is_sealable(self) -> None:
        skill = build_skill()
        assert {tool.name for tool in skill._pending} == {"list", "answer"}
        envelope = next(tool for tool in skill._pending if tool.name == "answer").handler(
            region="US",
            year=2026,
        )
        wire = envelope.to_wire()
        assert wire["payload"]["region"] == "US"
        assert verify_envelope_wire(wire, skill=skill) is True

    def test_registry_discovers_direct_endpoint(self) -> None:
        definition = next(item for item in builtin_registry() if item.name == "orrery/holidays")
        assert definition.direct_mcp_path == "/stars/holidays/mcp"

    def test_allowlist_regions_are_documented(self) -> None:
        assert "US" in REGIONS
        assert_payload_keys(
            list_holidays(region="JP", year=2026, clock=lambda: FIXED_TIME),
            ("region", "year", "holidays", "count", "source", "offline", "live_at_call"),
        )
