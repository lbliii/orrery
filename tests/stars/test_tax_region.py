"""Tests for orrery/tax-region — offline jurisdiction shape validation (#112)."""

from __future__ import annotations

import pytest

from dogfood import verify_receipt as verify_envelope_wire
from stars.tax_region.contract import tool_schemas
from stars.tax_region.corpus import CORPUS
from stars.tax_region.fixtures import DEFAULT_PROFILE, VALID_JURISDICTION
from stars.tax_region.service import validate
from stars.tax_region.skill import build_skill
from tests.stars.helpers import (
    assert_manifest_publish_corpus,
    assert_payload_keys,
    assert_tool_schema_keys,
    load_star_manifest,
)

GB_JURISDICTION = {
    "country": "GB",
    "region": "EN",
    "jurisdiction_key": "GB-EN",
}


@pytest.mark.issue(112)
class TestTaxRegionHappyPath:
    def test_valid_jurisdiction_returns_normalized_record_and_digest(self) -> None:
        first = validate(DEFAULT_PROFILE, VALID_JURISDICTION)
        second = validate(DEFAULT_PROFILE, VALID_JURISDICTION)
        assert first["valid"] is True
        assert first["normalized_jurisdiction"] == VALID_JURISDICTION
        assert first["profile_digest"] == second["profile_digest"]

    def test_second_allowlisted_jurisdiction_passes(self) -> None:
        result = validate(DEFAULT_PROFILE, GB_JURISDICTION)
        assert result["valid"] is True
        assert result["normalized_jurisdiction"] == GB_JURISDICTION


@pytest.mark.issue(112)
class TestTaxRegionValidationNegative:
    def test_invalid_pattern_type_missing_and_extra_fields_are_structured(self) -> None:
        result = validate(
            DEFAULT_PROFILE,
            {
                "country": "us",
                "region": 1,
                "jurisdiction_key": "US_CA",
                "extra": "nope",
            },
        )
        assert result["valid"] is False
        assert {(item["path"], item["code"]) for item in result["errors"]} == {
            ("$.country", "pattern"),
            ("$.region", "type"),
            ("$.jurisdiction_key", "pattern"),
            ("$.extra", "additional_property"),
        }

    def test_missing_required_field_reports_required(self) -> None:
        result = validate(DEFAULT_PROFILE, {"country": "US", "region": "CA"})
        assert result["valid"] is False
        assert result["errors"][0]["code"] == "required"

    def test_unknown_profile_fails_loud(self) -> None:
        result = validate("other", VALID_JURISDICTION)
        assert result["error"] == "profile_not_allowed"
        assert result["live_at_call"] is True


@pytest.mark.issue(112)
class TestTaxRegionContractAndEnvelope:
    def test_corpus_non_empty(self) -> None:
        assert len(CORPUS) >= 2

    def test_manifest_offline_policy_and_publish_corpus(self) -> None:
        manifest = load_star_manifest("tax_region")
        assert manifest["policy"]["allowed_egress"] == []
        assert_tool_schema_keys(tool_schemas(), {"validate"})
        assert_manifest_publish_corpus("tax_region")

    def test_skill_envelope_is_sealable(self) -> None:
        skill = build_skill()
        assert {tool.name for tool in skill._pending} == {"validate"}
        envelope = next(tool for tool in skill._pending if tool.name == "validate").handler(
            profile=DEFAULT_PROFILE,
            jurisdiction=VALID_JURISDICTION,
        )
        wire = envelope.to_wire()
        assert wire["payload"]["valid"] is True
        assert wire["payload"]["normalized_jurisdiction"] == VALID_JURISDICTION
        assert verify_envelope_wire(wire, skill=skill) is True

    def test_payload_keys_on_happy_path(self) -> None:
        assert_payload_keys(
            validate(DEFAULT_PROFILE, VALID_JURISDICTION),
            (
                "profile",
                "profile_version",
                "profile_digest",
                "valid",
                "errors",
                "live_at_call",
            ),
        )
