"""Tests for orrery/docs-myst-inventory — ADR 0008 analyze inventory (#169)."""

from __future__ import annotations

import copy

import pytest

from stars.docs_myst_inventory.contract import FEATURE_CLASSES, tool_schemas
from stars.docs_myst_inventory.fixtures import BASELINE_TREE, MALFORMED_TREE
from stars.docs_myst_inventory.service import inventory, verify_inventory
from stars.docs_myst_inventory.skill import build_skill
from tests.stars.helpers import (
    assert_manifest_publish_corpus,
    assert_payload_keys,
    assert_tool_schema_keys,
    load_star_manifest,
)


@pytest.mark.issue(169)
def test_inventory_digest_stable_for_unchanged_tree() -> None:
    first = inventory(BASELINE_TREE)
    second = inventory(BASELINE_TREE)
    assert first["inventory_digest"] == second["inventory_digest"]
    assert first["source_manifest_digest"] == second["source_manifest_digest"]
    assert verify_inventory(first) == {"verified": True}


@pytest.mark.issue(169)
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


@pytest.mark.issue(169)
def test_unsupported_and_decision_required_findings_are_visible() -> None:
    result = inventory(BASELINE_TREE)
    findings = result["findings"]
    feature_ids = {item["feature_id"] for item in findings}
    classes = {item["class"] for item in findings}

    assert "myst.directive.admonition" in feature_ids
    assert "myst.directive.include" in feature_ids
    assert "myst.ref.include" in feature_ids
    assert "myst.role.math" in feature_ids
    assert "myst.directive.toctree" in feature_ids
    assert "myst.directive.custom-macro" in feature_ids
    assert "myst.asset.image" in feature_ids
    assert "md.fenced_code" in feature_ids
    assert "md.heading" in feature_ids
    assert "md.link" in feature_ids

    assert "transformable" in classes
    assert "decision_required" in classes
    assert "unsupported" in classes
    assert "safe" in classes

    unsupported = [item for item in findings if item["class"] == "unsupported"]
    assert unsupported, "unsupported constructs must not be dropped"


@pytest.mark.issue(169)
def test_malformed_findings_for_broken_fences() -> None:
    result = inventory(MALFORMED_TREE)
    malformed = [item for item in result["findings"] if item["class"] == "malformed"]
    assert len(malformed) >= 2
    messages = " ".join(str(item.get("message", "")) for item in malformed)
    assert "unclosed" in messages


@pytest.mark.issue(169)
def test_findings_use_adr_0008_feature_classes_only() -> None:
    result = inventory(BASELINE_TREE + MALFORMED_TREE)
    for item in result["findings"]:
        assert item["class"] in FEATURE_CLASSES


@pytest.mark.issue(169)
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
        ),
    )
    serialized = str(result)
    for entry in BASELINE_TREE:
        assert entry["content"] not in serialized


@pytest.mark.issue(169)
def test_manifest_contract_and_tool_schema() -> None:
    manifest = load_star_manifest("docs_myst_inventory")
    assert manifest["star"]["name"] == "orrery/docs-myst-inventory"
    assert manifest["star"]["direct_mcp_path"] == "/stars/docs-myst-inventory/mcp"
    assert manifest["runtime"]["skill_factory"] == (
        "stars.docs_myst_inventory.skill:build_skill"
    )
    assert_manifest_publish_corpus("docs_myst_inventory")
    assert_tool_schema_keys(tool_schemas(), {"inventory"})


@pytest.mark.issue(169)
def test_skill_inventory_tool_round_trip() -> None:
    skill = build_skill()
    tool = next(item for item in skill._pending if item.name == "inventory")
    envelope = tool.handler(entries=BASELINE_TREE)
    payload = envelope.to_wire()["payload"]
    assert payload["inventory_digest"] == inventory(BASELINE_TREE)["inventory_digest"]
    assert verify_inventory(payload) == {"verified": True}
