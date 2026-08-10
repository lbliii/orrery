"""Tests for orrery/docs-rst-inventory — ADR 0008 analyze inventory (#173)."""

from __future__ import annotations

import copy

import pytest

from stars.docs_rst_inventory.contract import FEATURE_CLASSES, tool_schemas
from stars.docs_rst_inventory.fixtures import BASELINE_TREE, MALFORMED_TREE, SAFE_ONLY_TREE
from stars.docs_rst_inventory.service import inventory, verify_inventory
from stars.docs_rst_inventory.skill import build_skill
from tests.stars.helpers import (
    assert_manifest_publish_corpus,
    assert_payload_keys,
    assert_tool_schema_keys,
    load_star_manifest,
)


@pytest.mark.issue(173)
def test_inventory_digest_stable_for_unchanged_tree() -> None:
    first = inventory(BASELINE_TREE)
    second = inventory(BASELINE_TREE)
    assert first["inventory_digest"] == second["inventory_digest"]
    assert first["source_manifest_digest"] == second["source_manifest_digest"]
    assert verify_inventory(first) == {"verified": True}


@pytest.mark.issue(173)
def test_inventory_digest_changes_when_tree_changes() -> None:
    baseline = inventory(BASELINE_TREE)
    mutated = copy.deepcopy(BASELINE_TREE)
    mutated[0] = {
        **mutated[0],
        "content": mutated[0]["content"].replace("Welcome", "Welcome back"),
    }
    changed = inventory(mutated)
    assert changed["inventory_digest"] != baseline["inventory_digest"]
    assert changed["source_manifest_digest"] != baseline["source_manifest_digest"]


@pytest.mark.issue(173)
def test_representative_sphinx_constructs_are_classified() -> None:
    result = inventory(BASELINE_TREE)
    findings = result["findings"]
    feature_ids = {item["feature_id"] for item in findings}
    classes = {item["class"] for item in findings}

    assert "rst.heading" in feature_ids
    assert "rst.directive.admonition" in feature_ids
    assert "rst.directive.include" in feature_ids
    assert "rst.ref.include" in feature_ids
    assert "rst.directive.toctree" in feature_ids
    assert "rst.directive.table" in feature_ids
    assert "rst.directive.automodule" in feature_ids
    assert "rst.directive.raw" in feature_ids
    assert "rst.directive.custom-macro" in feature_ids
    assert "rst.directive.code-block" in feature_ids
    assert "rst.asset.image" in feature_ids
    assert "rst.substitution.definition" in feature_ids
    assert "rst.substitution.reference" in feature_ids
    assert "rst.role.ref" in feature_ids
    assert "rst.role.math" in feature_ids
    assert "rst.role.func" in feature_ids

    assert "safe" in classes
    assert "transformable" in classes
    assert "decision_required" in classes
    assert "unsupported" in classes

    for item in findings:
        span = item["span"]
        assert isinstance(span["line"], int) and span["line"] >= 1
        assert isinstance(span["column"], int) and span["column"] >= 1


@pytest.mark.issue(173)
def test_ineligibility_reasons_explain_blocked_conversion() -> None:
    result = inventory(BASELINE_TREE)
    assert result["conversion_eligible"] is False
    reasons = result["ineligibility_reasons"]
    assert reasons, "blocking findings must explain why conversion is not eligible"
    reason_ids = {item["feature_id"] for item in reasons}
    assert "rst.directive.automodule" in reason_ids
    assert "rst.directive.raw" in reason_ids
    assert "rst.directive.include" in reason_ids
    assert "rst.directive.toctree" in reason_ids
    blocking = {"decision_required", "unsupported", "malformed"}
    assert all(item["class"] in blocking for item in reasons)


@pytest.mark.issue(173)
def test_safe_only_tree_is_conversion_eligible() -> None:
    result = inventory(SAFE_ONLY_TREE)
    assert result["conversion_eligible"] is True
    assert result["ineligibility_reasons"] == []
    classes = {item["class"] for item in result["findings"]}
    assert classes <= {"safe", "transformable"}


@pytest.mark.issue(173)
def test_malformed_findings_for_orphan_ellipsis() -> None:
    result = inventory(MALFORMED_TREE)
    malformed = [item for item in result["findings"] if item["class"] == "malformed"]
    assert malformed
    messages = " ".join(str(item.get("message", "")) for item in malformed)
    assert "orphan" in messages
    assert result["conversion_eligible"] is False


@pytest.mark.issue(173)
def test_findings_use_adr_0008_feature_classes_only() -> None:
    result = inventory(BASELINE_TREE + MALFORMED_TREE)
    for item in result["findings"]:
        assert item["class"] in FEATURE_CLASSES


@pytest.mark.issue(173)
def test_inventory_payload_shape_and_no_raw_content_echo() -> None:
    result = inventory(BASELINE_TREE)
    assert_payload_keys(
        result,
        (
            "source_manifest_digest",
            "findings",
            "inventory_digest",
            "analysis_digest",
            "entry_count",
            "finding_count",
            "findings_truncated",
            "conversion_eligible",
            "ineligibility_reasons",
        ),
    )
    serialized = str(result)
    for entry in BASELINE_TREE:
        assert entry["content"] not in serialized


@pytest.mark.issue(173)
def test_manifest_contract_and_tool_schema() -> None:
    manifest = load_star_manifest("docs_rst_inventory")
    assert manifest["star"]["name"] == "orrery/docs-rst-inventory"
    assert manifest["star"]["direct_mcp_path"] == "/stars/docs-rst-inventory/mcp"
    assert manifest["runtime"]["skill_factory"] == (
        "stars.docs_rst_inventory.skill:build_skill"
    )
    assert_manifest_publish_corpus("docs_rst_inventory")
    assert_tool_schema_keys(tool_schemas(), {"inventory"})


@pytest.mark.issue(173)
def test_skill_inventory_tool_round_trip() -> None:
    skill = build_skill()
    tool = next(item for item in skill._pending if item.name == "inventory")
    envelope = tool.handler(entries=BASELINE_TREE)
    payload = envelope.to_wire()["payload"]
    assert payload["inventory_digest"] == inventory(BASELINE_TREE)["inventory_digest"]
    assert verify_inventory(payload) == {"verified": True}
