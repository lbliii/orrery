"""Tests for orrery/flight-status — offline allowlisted flight schedule/status (#105)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from dogfood import verify_receipt as verify_envelope_wire
from stars.builtins import builtin_registry
from stars.flight_status.contract import tool_schemas
from stars.flight_status.corpus import CORPUS
from stars.flight_status.fixtures import (
    DEFAULT_ARRIVAL,
    DEFAULT_DEPARTURE,
    DEFAULT_FLIGHT,
    DEFAULT_STATUS,
)
from stars.flight_status.flights import SCHEDULE
from stars.flight_status.service import answer, status
from stars.flight_status.skill import build_skill
from tests.stars.helpers import (
    assert_allowlist_rejects,
    assert_manifest_publish_corpus,
    assert_payload_keys,
    assert_tool_schema_keys,
    load_star_manifest,
)

FIXED_TIME = datetime(2026, 8, 11, 12, 0, 0, tzinfo=UTC)


@pytest.mark.issue(105)
class TestFlightStatusHappyPath:
    def test_allowlisted_flight_and_date_returns_status_fields(self) -> None:
        record = SCHEDULE[("AA100", "2026-08-11")]
        result = status(flight="AA100", date="2026-08-11", clock=lambda: FIXED_TIME)
        assert result == {
            "flight": "AA100",
            "date": "2026-08-11",
            "status": str(record["status"]),
            "departure_airport": str(record["departure_airport"]),
            "arrival_airport": str(record["arrival_airport"]),
            "scheduled_departure": str(record["scheduled_departure"]),
            "scheduled_arrival": str(record["scheduled_arrival"]),
            "carrier": str(record["carrier"]),
            "provider": "orrery-fixtures",
            "source": "flight:AA100:2026-08-11",
            "observed_at": FIXED_TIME.isoformat(),
            "offline": True,
            "live_at_call": True,
        }

    def test_delayed_fixture_includes_delay_minutes(self) -> None:
        result = status(flight="AA100", date="2026-08-12", clock=lambda: FIXED_TIME)
        assert result["status"] == "delayed"
        assert result["delay_minutes"] == 45
        assert result["actual_departure"] == "08:45"

    def test_answer_wraps_status_lookup(self) -> None:
        result = answer(flight=DEFAULT_FLIGHT, date="2026-08-11")
        assert result["status"] == DEFAULT_STATUS
        assert result["departure_airport"] == DEFAULT_DEPARTURE
        assert result["arrival_airport"] == DEFAULT_ARRIVAL
        assert result["answer"] == (
            f"{DEFAULT_FLIGHT} {DEFAULT_DEPARTURE}→{DEFAULT_ARRIVAL} is {DEFAULT_STATUS}"
        )


@pytest.mark.issue(105)
class TestFlightStatusAllowlistNegative:
    def test_out_of_allowlist_flight_fails_loud(self) -> None:
        result = assert_allowlist_rejects(
            status,
            flight="ZZ999",
            date="2026-08-11",
            error="flight_not_allowed",
            clock=lambda: FIXED_TIME,
        )
        assert result["live_at_call"] is True

    def test_unknown_date_fails_loud(self) -> None:
        result = assert_allowlist_rejects(
            status,
            flight="AA100",
            date="2099-01-01",
            error="date_not_available",
            clock=lambda: FIXED_TIME,
        )
        assert "pinned_dates" in result


@pytest.mark.issue(105)
class TestFlightStatusContractAndEnvelope:
    def test_corpus_non_empty(self) -> None:
        assert len(CORPUS) >= 2

    def test_manifest_offline_policy_and_publish_corpus(self) -> None:
        manifest = load_star_manifest("flight_status")
        assert manifest["policy"]["allowed_egress"] == []
        assert_tool_schema_keys(tool_schemas(), {"status", "answer"})
        assert_manifest_publish_corpus("flight_status")

    def test_skill_envelope_is_sealable(self) -> None:
        skill = build_skill()
        assert {tool.name for tool in skill._pending} == {"status", "answer"}
        envelope = next(tool for tool in skill._pending if tool.name == "answer").handler(
            flight="UA456", date="2026-08-11"
        )
        wire = envelope.to_wire()
        assert wire["payload"]["status"] == "landed"
        assert verify_envelope_wire(wire, skill=skill) is True

    def test_registry_discovers_direct_endpoint(self) -> None:
        definition = next(
            item for item in builtin_registry() if item.name == "orrery/flight-status"
        )
        assert definition.direct_mcp_path == "/stars/flight-status/mcp"

    def test_payload_keys_on_happy_path(self) -> None:
        assert_payload_keys(
            status(flight="BA178", date="2026-08-11", clock=lambda: FIXED_TIME),
            (
                "flight",
                "date",
                "status",
                "departure_airport",
                "arrival_airport",
                "provider",
                "offline",
                "live_at_call",
            ),
        )
