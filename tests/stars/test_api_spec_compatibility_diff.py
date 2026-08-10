"""Tests for orrery/api-spec-compatibility-diff — ADR 0008 policy (#176)."""

from __future__ import annotations

import copy

import pytest

from stars.api_spec_compatibility_diff.contract import (
    CHANGE_CLASSIFICATIONS,
    tool_schemas,
)
from stars.api_spec_compatibility_diff.fixtures import (
    ADDITIVE_TARGET,
    AMBIGUOUS_TARGET,
    BASELINE_POLICY,
    BREAKING_TARGET,
    INFO_TARGET,
    SOURCE_SPEC,
)
from stars.api_spec_compatibility_diff.service import compatibility_diff, verify_diff
from stars.api_spec_compatibility_diff.skill import build_skill
from tests.stars.helpers import (
    assert_manifest_publish_corpus,
    assert_payload_keys,
    assert_tool_schema_keys,
    load_star_manifest,
)


@pytest.mark.issue(176)
def test_known_breaking_fixture_is_flagged() -> None:
    result = compatibility_diff(SOURCE_SPEC, BREAKING_TARGET, BASELINE_POLICY)
    assert "error" not in result
    assert result["runtime_compatibility_claimed"] is False
    removals = [item for item in result["changes"] if item["rule_id"] == "breaking.path.remove"]
    assert removals, "path removal must surface as breaking.path.remove"
    assert removals[0]["classification"] == "breaking"
    assert removals[0]["action"] == "block"
    assert removals[0]["location"].startswith("/paths/")
    assert removals[0]["location_kind"] == "operation"
    assert verify_diff(result) == {"verified": True}


@pytest.mark.issue(176)
def test_policy_changes_alter_classification_transparently() -> None:
    baseline = compatibility_diff(SOURCE_SPEC, BREAKING_TARGET, BASELINE_POLICY)
    assert baseline["changes"][0]["classification"] == "breaking"

    softened = copy.deepcopy(BASELINE_POLICY)
    softened["rules"] = [
        {
            "id": "breaking.path.remove",
            "severity": "informational",
            "action": "report",
        },
        BASELINE_POLICY["rules"][1],
    ]
    soft = compatibility_diff(SOURCE_SPEC, BREAKING_TARGET, softened)
    soft_removals = [item for item in soft["changes"] if item["rule_id"] == "breaking.path.remove"]
    assert soft_removals
    assert soft_removals[0]["classification"] == "informational"
    assert soft_removals[0]["action"] == "report"
    assert soft["diff_digest"] != baseline["diff_digest"]
    assert soft["policy_digest"] != baseline["policy_digest"]

    exempt_policy = copy.deepcopy(BASELINE_POLICY)
    exempt_policy["rules"] = [
        {
            "id": "breaking.path.remove",
            "severity": "breaking",
            "action": "allow",
        }
    ]
    exempt = compatibility_diff(SOURCE_SPEC, BREAKING_TARGET, exempt_policy)
    exempt_removals = [
        item for item in exempt["changes"] if item["rule_id"] == "breaking.path.remove"
    ]
    assert exempt_removals[0]["classification"] == "policy-exempt"


@pytest.mark.issue(176)
def test_ambiguous_changes_remain_unknown_decision_required() -> None:
    result = compatibility_diff(SOURCE_SPEC, AMBIGUOUS_TARGET, BASELINE_POLICY)
    assert "error" not in result
    ambiguous = [item for item in result["changes"] if item["rule_id"] == "unknown.schema.change"]
    assert ambiguous
    assert ambiguous[0]["classification"] == "unknown"
    assert ambiguous[0]["action"] == "decision_required"
    assert ambiguous[0]["location"].startswith("/components/schemas/")


@pytest.mark.issue(176)
def test_additive_and_policy_exempt_info_change() -> None:
    additive = compatibility_diff(SOURCE_SPEC, ADDITIVE_TARGET, BASELINE_POLICY)
    assert "error" not in additive
    adds = [item for item in additive["changes"] if item["classification"] == "additive"]
    assert adds
    assert any(item["location_kind"] == "operation" for item in adds)
    assert any(item["location_kind"] == "schema" for item in adds)

    info = compatibility_diff(SOURCE_SPEC, INFO_TARGET, BASELINE_POLICY)
    assert "error" not in info
    desc = [item for item in info["changes"] if item["rule_id"] == "info.description.change"]
    assert desc
    assert desc[0]["classification"] == "policy-exempt"
    assert desc[0]["action"] == "allow"


@pytest.mark.issue(176)
def test_result_bounded_receipt_ready_and_no_runtime_claim() -> None:
    result = compatibility_diff(SOURCE_SPEC, BREAKING_TARGET, BASELINE_POLICY)
    assert_payload_keys(
        result,
        (
            "policy_id",
            "policy_digest",
            "source_manifest_digest",
            "target_manifest_digest",
            "source_analysis_digest",
            "target_analysis_digest",
            "changes",
            "changes_truncated",
            "runtime_compatibility_claimed",
            "diff_digest",
            "change_count",
            "source_entry_count",
            "target_entry_count",
            "compatibility_policy",
        ),
    )
    assert result["runtime_compatibility_claimed"] is False
    assert result["changes_truncated"] is False
    assert result["change_count"] == len(result["changes"])
    serialized = str(result)
    for entry in SOURCE_SPEC + BREAKING_TARGET:
        assert entry["content"] not in serialized
    for item in result["changes"]:
        assert item["classification"] in CHANGE_CLASSIFICATIONS
        assert "change_digest" in item


@pytest.mark.issue(176)
def test_rejects_parallel_policy_schema() -> None:
    bad = copy.deepcopy(BASELINE_POLICY)
    bad["extra"] = "side-channel"
    rejected = compatibility_diff(SOURCE_SPEC, BREAKING_TARGET, bad)
    assert rejected["error"] == "compatibility_policy_shape_invalid"


@pytest.mark.issue(176)
def test_manifest_contract_and_tool_schema() -> None:
    manifest = load_star_manifest("api_spec_compatibility_diff")
    assert manifest["star"]["name"] == "orrery/api-spec-compatibility-diff"
    assert manifest["star"]["direct_mcp_path"] == "/stars/api-spec-compatibility-diff/mcp"
    assert manifest["runtime"]["skill_factory"] == (
        "stars.api_spec_compatibility_diff.skill:build_skill"
    )
    assert_manifest_publish_corpus("api_spec_compatibility_diff")
    assert_tool_schema_keys(tool_schemas(), {"diff"})


@pytest.mark.issue(176)
def test_skill_diff_round_trip() -> None:
    skill = build_skill()
    pending = {item.name: item for item in skill._pending}
    envelope = pending["diff"].handler(
        source_entries=SOURCE_SPEC,
        target_entries=BREAKING_TARGET,
        compatibility_policy=BASELINE_POLICY,
    )
    payload = envelope.to_wire()["payload"]
    direct = compatibility_diff(SOURCE_SPEC, BREAKING_TARGET, BASELINE_POLICY)
    assert payload["diff_digest"] == direct["diff_digest"]
    assert payload["runtime_compatibility_claimed"] is False
