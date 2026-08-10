"""Tests for orrery/docs-mdx-validate-and-migration-diff — ADR 0008 (#172)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from stars._core.migration_run import MigrationRunStore, build_change_bundle
from stars.docs_mdx_validate_and_migration_diff.contract import tool_schemas
from stars.docs_mdx_validate_and_migration_diff.fixtures import (
    BUILD_FAIL_TARGET,
    LINK_ASSET_REPORT_UNRESOLVED,
    SAFE_SOURCE,
    SAFE_TARGET,
    SEMANTIC_LOSS_TARGET,
)
from stars.docs_mdx_validate_and_migration_diff.service import validate
from stars.docs_mdx_validate_and_migration_diff.skill import build_skill
from stars.docs_myst_to_mdx_safe.fixtures import SAFE_TREE
from stars.docs_myst_to_mdx_safe.service import apply, plan
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


def _sealed_apply(
    source: list[dict[str, str]], profile: dict[str, object]
) -> tuple[dict[str, object], dict[str, object]]:
    planned = plan(source, profile)
    assert "error" not in planned
    applied = apply(source, planned, profile)
    assert "error" not in applied
    return planned, applied


def _bundle_for_paths(
    paths: list[str], *, plan_digest: str = "a" * 64
) -> dict[str, object]:
    file_entries = [
        {
            "path": path,
            "source_digest": "b" * 64,
            "target_digest": "c" * 64,
        }
        for path in sorted(paths)
    ]
    return build_change_bundle(
        plan_digest=plan_digest,
        patch_digest="d" * 64,
        file_entries=file_entries,
        mapping_digest="e" * 64,
        warnings=[],
    )


@pytest.mark.issue(172)
def test_safe_producer_bundle_validates_clean(
    baseline_profile: dict[str, object],
) -> None:
    planned, applied = _sealed_apply(SAFE_TREE, baseline_profile)
    result = validate(
        SAFE_TREE,
        applied["targets"],
        applied["change_bundle"],
        baseline_profile,
        plan=planned,
    )
    assert "error" not in result
    assert result["validation_passed"] is True
    assert result["validation"]["passed"] is True
    assert result["build_status"]["passed"] is True
    assert result["migration_diff"]["mapping_coverage"]["complete"] is True
    assert result["report_digest"]
    assert len(result["report_digest"]) == 64
    assert_payload_keys(
        result["validation"],
        (
            "bundle_digest",
            "validator",
            "passed",
            "findings",
            "diagnostics_digest",
            "validation_digest",
        ),
    )
    assert result["validator"]["name"] == "orrery/docs-mdx-validate"


@pytest.mark.issue(172)
def test_validation_failure_seals_failed_stage(
    baseline_profile: dict[str, object],
) -> None:
    bundle = _bundle_for_paths(["guide.md", "index.md"])
    store = MigrationRunStore()
    result = validate(
        SAFE_SOURCE,
        BUILD_FAIL_TARGET,
        bundle,
        baseline_profile,
        store=store,
    )
    assert "error" not in result
    assert result["validation_passed"] is False
    assert result["validation"]["passed"] is False
    sealed = result["sealed_stage"]
    assert sealed["validation_passed"] is False
    assert sealed["output"]["passed"] is False
    assert sealed["mode"] == "validate"
    assert any(
        item.get("feature_id") == "mdx.admonition.unbalanced"
        for item in result["findings"]
    )


@pytest.mark.issue(172)
def test_semantic_loss_visible_when_syntax_passes(
    baseline_profile: dict[str, object],
) -> None:
    bundle = _bundle_for_paths(["guide.md", "index.md"])
    result = validate(
        SAFE_SOURCE,
        SEMANTIC_LOSS_TARGET,
        bundle,
        baseline_profile,
        link_asset_report=LINK_ASSET_REPORT_UNRESOLVED,
    )
    assert "error" not in result
    assert result["build_status"]["passed"] is True
    # Syntax build may pass while semantic-loss findings remain visible.
    assert result["validation_passed"] is True
    feature_ids = {item["feature_id"] for item in result["findings"]}
    assert "myst.directive.admonition" in feature_ids
    assert "md.link.unresolved" in feature_ids
    assert "md.asset.unresolved" in feature_ids
    dropped = result["migration_diff"]["dropped_constructs"]
    assert any(row["feature_id"] == "myst.directive.admonition" for row in dropped)
    assert result["migration_diff"]["unresolved_links"]
    assert result["migration_diff"]["unresolved_assets"]
    # Diagnostics stay bounded / redacted (no raw source).
    assert "source_bytes" not in str(result["diagnostics"])
    assert "```{note}" not in str(result["diagnostics"])


@pytest.mark.issue(172)
def test_rejects_tampered_bundle_and_plan_mismatch(
    baseline_profile: dict[str, object],
) -> None:
    planned, applied = _sealed_apply(SAFE_TREE, baseline_profile)
    tampered = copy.deepcopy(applied["change_bundle"])
    tampered["bundle_digest"] = "f" * 64
    rejected = validate(
        SAFE_TREE,
        applied["targets"],
        tampered,
        baseline_profile,
        plan=planned,
    )
    assert rejected["error"] == "bundle_digest_mismatch"

    mismatch_plan = copy.deepcopy(planned)
    mismatch_plan["plan_digest"] = "0" * 64
    rejected_plan = validate(
        SAFE_TREE,
        applied["targets"],
        applied["change_bundle"],
        baseline_profile,
        plan=mismatch_plan,
    )
    assert rejected_plan["error"] == "plan_digest_mismatch"


@pytest.mark.issue(172)
def test_mapping_coverage_gap_surfaces_finding(
    baseline_profile: dict[str, object],
) -> None:
    # Bundle maps only one of two source paths.
    bundle = _bundle_for_paths(["index.md"])
    result = validate(
        SAFE_SOURCE,
        SAFE_TARGET,
        bundle,
        baseline_profile,
    )
    assert "error" not in result
    coverage = result["migration_diff"]["mapping_coverage"]
    assert coverage["complete"] is False
    assert "guide.md" in coverage["missing_paths"]
    assert any(
        item["feature_id"] == "migration.mapping.coverage"
        for item in result["findings"]
    )


@pytest.mark.issue(172)
def test_manifest_contract_and_tool_schema() -> None:
    manifest = load_star_manifest("docs_mdx_validate_and_migration_diff")
    assert manifest["star"]["name"] == "orrery/docs-mdx-validate-and-migration-diff"
    assert manifest["star"]["direct_mcp_path"] == (
        "/stars/docs-mdx-validate-and-migration-diff/mcp"
    )
    assert manifest["runtime"]["skill_factory"] == (
        "stars.docs_mdx_validate_and_migration_diff.skill:build_skill"
    )
    assert_manifest_publish_corpus("docs_mdx_validate_and_migration_diff")
    assert_tool_schema_keys(tool_schemas(), {"validate"})


@pytest.mark.issue(172)
def test_skill_validate_round_trip(baseline_profile: dict[str, object]) -> None:
    planned, applied = _sealed_apply(SAFE_TREE, baseline_profile)
    skill = build_skill()
    pending = {item.name: item for item in skill._pending}
    envelope = pending["validate"].handler(
        source_entries=SAFE_TREE,
        target_entries=applied["targets"],
        change_bundle=applied["change_bundle"],
        profile=baseline_profile,
        plan=planned,
    )
    payload = envelope.to_wire()["payload"]
    direct = validate(
        SAFE_TREE,
        applied["targets"],
        applied["change_bundle"],
        baseline_profile,
        plan=planned,
    )
    assert payload["validation_digest"] == direct["validation_digest"]
    assert payload["report_digest"] == direct["report_digest"]
    assert payload["validation_passed"] is True
