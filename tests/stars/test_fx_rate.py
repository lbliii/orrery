"""Tests for orrery/fx-rate — offline allowlisted FX as-of lookup (#111)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from dogfood import verify_receipt as verify_envelope_wire
from stars.fx_rate.contract import tool_schemas
from stars.fx_rate.corpus import CORPUS
from stars.fx_rate.fixtures import (
    DEFAULT_AS_OF,
    DEFAULT_BASE,
    DEFAULT_PAIR,
    DEFAULT_QUOTE,
    DEFAULT_RATE,
)
from stars.fx_rate.rates import PAIRS, PINNED_AS_OF
from stars.fx_rate.service import answer, fx_rate
from stars.fx_rate.skill import build_skill
from tests.stars.helpers import (
    assert_allowlist_rejects,
    assert_manifest_publish_corpus,
    assert_payload_keys,
    assert_tool_schema_keys,
    load_star_manifest,
)

FIXED_TIME = datetime(2026, 8, 11, 12, 0, 0, tzinfo=UTC)


@pytest.mark.issue(111)
class TestFxRateHappyPath:
    def test_allowlisted_pair_returns_pinned_rate(self) -> None:
        result = fx_rate(
            pair=DEFAULT_PAIR,
            as_of=DEFAULT_AS_OF,
            clock=lambda: FIXED_TIME,
        )
        assert result == {
            "pair": DEFAULT_PAIR,
            "base": DEFAULT_BASE,
            "quote": DEFAULT_QUOTE,
            "rate": DEFAULT_RATE,
            "as_of": DEFAULT_AS_OF,
            "provider": "orrery-fixtures",
            "source": "static:orrery/fx-rate-v1",
            "observed_at": FIXED_TIME.isoformat(),
            "offline": True,
            "live_at_call": True,
        }

    def test_answer_wraps_fx_rate(self) -> None:
        result = answer(pair="usd-jpy", as_of="2026-08-01", clock=lambda: FIXED_TIME)
        assert result["base"] == "USD"
        assert result["quote"] == "JPY"
        assert result["rate"] == 147.35
        assert result["answer"] == "1 USD = 147.35 JPY as of 2026-08-01"


@pytest.mark.issue(111)
class TestFxRateAllowlistNegative:
    def test_out_of_allowlist_pair_fails_loud(self) -> None:
        result = assert_allowlist_rejects(
            fx_rate,
            pair="btc-usd",
            as_of=DEFAULT_AS_OF,
            error="pair_not_allowed",
            clock=lambda: FIXED_TIME,
        )
        assert result["live_at_call"] is True

    def test_unpinned_as_of_fails_loud(self) -> None:
        result = fx_rate(
            pair=DEFAULT_PAIR,
            as_of="1999-01-01",
            clock=lambda: FIXED_TIME,
        )
        assert result["error"] == "as_of_not_available"
        assert result["live_at_call"] is True


@pytest.mark.issue(111)
class TestFxRateContractAndEnvelope:
    def test_corpus_non_empty(self) -> None:
        assert len(CORPUS) >= 2

    def test_manifest_offline_policy_and_publish_corpus(self) -> None:
        manifest = load_star_manifest("fx_rate")
        assert manifest["policy"]["allowed_egress"] == []
        assert_tool_schema_keys(tool_schemas(), {"fx_rate", "answer"})
        assert_manifest_publish_corpus("fx_rate")

    def test_skill_envelope_is_sealable(self) -> None:
        skill = build_skill()
        assert {tool.name for tool in skill._pending} == {"fx_rate", "answer"}
        envelope = next(tool for tool in skill._pending if tool.name == "answer").handler(
            pair="eur-gbp",
            as_of="2026-01-15",
        )
        wire = envelope.to_wire()
        assert wire["payload"]["base"] == "EUR"
        assert verify_envelope_wire(wire, skill=skill) is True

    def test_allowlist_pairs_and_dates_are_documented(self) -> None:
        assert "usd-eur" in PAIRS
        assert DEFAULT_AS_OF in PINNED_AS_OF
        assert_payload_keys(
            fx_rate(pair="eur-usd", as_of="2026-06-01", clock=lambda: FIXED_TIME),
            (
                "pair",
                "base",
                "quote",
                "rate",
                "as_of",
                "provider",
                "offline",
                "live_at_call",
            ),
        )
