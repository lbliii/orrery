"""Tests for orrery/docs-myst-to-mdx-safe — ADR 0008 plan/apply (#170)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from stars.docs_myst_to_mdx_safe.contract import CORPUS_FEATURES, tool_schemas
from stars.docs_myst_to_mdx_safe.fixtures import MALFORMED_TREE, SAFE_TREE, UNSUPPORTED_TREE
from stars.docs_myst_to_mdx_safe.service import apply, plan
from stars.docs_myst_to_mdx_safe.skill import build_skill
from stars.docs_myst_to_mdx_safe.transform import baseline_mdx_buildable
from tests.stars.helpers import (
    assert_manifest_publish_corpus,
    assert_payload_keys,
    assert_tool_schema_keys,
    load_star_manifest,
)

_PROFILE_PATH = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "migration"
    / "profiles"
    / "docs_myst_to_mdx_baseline.json"
)


@pytest.fixture
def baseline_profile() -> dict[str, object]:
    return json.loads(_PROFILE_PATH.read_text(encoding="utf-8"))


@pytest.mark.issue(170)
def test_safe_fixtures_produce_baseline_buildable_targets(
    baseline_profile: dict[str, object],
) -> None:
    planned = plan(SAFE_TREE, baseline_profile)
    assert "error" not in planned
    assert any(op["op"] == "copy_heading" for op in planned["planned_ops"])
    assert any(op["op"] == "transform_admonition" for op in planned["planned_ops"])

    result = apply(SAFE_TREE, planned, baseline_profile)
    assert "error" not in result
    bundle = result["change_bundle"]
    assert_payload_keys(
        bundle,
        (
            "plan_digest",
            "patch_digest",
            "file_entries",
            "mapping_digest",
            "warnings",
            "bundle_digest",
        ),
    )
    assert result["plan_digest"] == planned["plan_digest"]

    targets = {item["path"]: item["content"] for item in result["targets"]}
    assert "# Welcome" in targets["index.md"]
    assert '<Admonition type="note">' in targets["index.md"]
    assert "</Admonition>" in targets["index.md"]
    assert "```{note}" not in targets["index.md"]
    assert "## Guide" in targets["guide.md"]

    # File mapping preserved (same relative paths).
    assert {item["path"] for item in bundle["file_entries"]} == {"guide.md", "index.md"}
    for entry in bundle["file_entries"]:
        assert entry["source_digest"] and entry["target_digest"]

    validation = result["baseline_validation"]
    assert validation["passed"] is True
    assert baseline_mdx_buildable(result["targets"])["passed"] is True


@pytest.mark.issue(170)
def test_unsupported_fixtures_are_surfaced_not_stripped(
    baseline_profile: dict[str, object],
) -> None:
    planned = plan(UNSUPPORTED_TREE, baseline_profile)
    assert "error" not in planned
    findings = planned["findings"]
    feature_ids = {item["feature_id"] for item in findings}
    classes = {item["class"] for item in findings}

    assert "myst.directive.include" in feature_ids
    assert "myst.directive.custom-macro" in feature_ids
    assert "myst.role.math" in feature_ids
    assert "myst.role.ref" in feature_ids
    assert "decision_required" in classes or "unsupported" in classes

    hold_ops = [op for op in planned["planned_ops"] if op["op"] == "hold"]
    assert hold_ops, "unsupported constructs must produce hold ops"

    result = apply(UNSUPPORTED_TREE, planned, baseline_profile)
    assert "error" not in result
    targets = {item["path"]: item["content"] for item in result["targets"]}

    # Original unsupported syntax preserved — not silently plain-texted.
    assert "```{include} partial.md" in targets["includes.md"]
    assert "::: {custom-macro}" in targets["custom.md"]
    assert "{ref}`intro`" in targets["roles.md"]
    assert "{math}`x^2`" in targets["roles.md"]
    assert targets["includes.md"].strip() != "include"

    for entry in result["change_bundle"]["file_entries"]:
        assert entry["source_digest"] == entry["target_digest"]


@pytest.mark.issue(170)
def test_malformed_findings_hold_without_silent_repair(
    baseline_profile: dict[str, object],
) -> None:
    planned = plan(MALFORMED_TREE, baseline_profile)
    malformed = [item for item in planned["findings"] if item["class"] == "malformed"]
    assert malformed
    result = apply(MALFORMED_TREE, planned, baseline_profile)
    assert "error" not in result
    target = result["targets"][0]["content"]
    assert "```{note}" in target
    assert target == MALFORMED_TREE[0]["content"].replace("\r\n", "\n")


@pytest.mark.issue(170)
def test_apply_idempotent_and_rejects_digest_mismatch(
    baseline_profile: dict[str, object],
) -> None:
    planned = plan(SAFE_TREE, baseline_profile)
    first = apply(SAFE_TREE, planned, baseline_profile)
    second = apply(SAFE_TREE, planned, baseline_profile)
    assert first["bundle_digest"] == second["bundle_digest"]
    assert first["change_bundle"] == second["change_bundle"]

    mutated = copy.deepcopy(SAFE_TREE)
    mutated[0] = {
        **mutated[0],
        "content": mutated[0]["content"].replace("Welcome", "Welcome back"),
    }
    rejected_source = apply(mutated, planned, baseline_profile)
    assert rejected_source["error"] == "source_digest_mismatch"

    other_profile = copy.deepcopy(baseline_profile)
    other_profile["profile_digest"] = "c" * 64
    rejected_profile = apply(SAFE_TREE, planned, other_profile)
    assert rejected_profile["error"] in {"profile_invalid", "profile_digest_mismatch"}


@pytest.mark.issue(170)
def test_plan_findings_use_adr_classes_only(
    baseline_profile: dict[str, object],
) -> None:
    planned = plan(SAFE_TREE + UNSUPPORTED_TREE + MALFORMED_TREE, baseline_profile)
    for item in planned["findings"]:
        assert item["class"] in {
            "safe",
            "transformable",
            "decision_required",
            "unsupported",
            "malformed",
        }
    corpus_ops = [
        op
        for op in planned["planned_ops"]
        if op.get("feature_id") in CORPUS_FEATURES and op["op"] != "hold"
    ]
    assert corpus_ops


@pytest.mark.issue(170)
def test_manifest_contract_and_tool_schema() -> None:
    manifest = load_star_manifest("docs_myst_to_mdx_safe")
    assert manifest["star"]["name"] == "orrery/docs-myst-to-mdx-safe"
    assert manifest["star"]["direct_mcp_path"] == "/stars/docs-myst-to-mdx-safe/mcp"
    assert manifest["runtime"]["skill_factory"] == (
        "stars.docs_myst_to_mdx_safe.skill:build_skill"
    )
    assert_manifest_publish_corpus("docs_myst_to_mdx_safe")
    assert_tool_schema_keys(tool_schemas(), {"plan", "apply"})


@pytest.mark.issue(170)
def test_skill_plan_apply_round_trip(baseline_profile: dict[str, object]) -> None:
    skill = build_skill()
    pending = {item.name: item for item in skill._pending}
    plan_envelope = pending["plan"].handler(entries=SAFE_TREE, profile=baseline_profile)
    plan_payload = plan_envelope.to_wire()["payload"]
    assert plan_payload["plan_digest"] == plan(SAFE_TREE, baseline_profile)["plan_digest"]

    apply_envelope = pending["apply"].handler(
        entries=SAFE_TREE,
        plan=plan_payload,
        profile=baseline_profile,
    )
    apply_payload = apply_envelope.to_wire()["payload"]
    assert apply_payload["bundle_digest"] == apply(SAFE_TREE, plan_payload, baseline_profile)[
        "bundle_digest"
    ]
    assert apply_payload["baseline_validation"]["passed"] is True
