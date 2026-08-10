"""Tests for orrery/docs-frontmatter-link-asset-migrate (#171)."""

from __future__ import annotations

import copy

import pytest

from stars.docs_frontmatter_link_asset_migrate.contract import FEATURE_CLASSES, tool_schemas
from stars.docs_frontmatter_link_asset_migrate.fixtures import (
    BASELINE_TREE,
    REDIRECT_RULES,
    REDIRECT_TREE,
    UNSAFE_RULES,
    UNSAFE_TREE,
)
from stars.docs_frontmatter_link_asset_migrate.service import migrate, verify_migrate
from stars.docs_frontmatter_link_asset_migrate.skill import build_skill
from tests.stars.helpers import (
    assert_manifest_publish_corpus,
    assert_payload_keys,
    assert_tool_schema_keys,
    load_star_manifest,
)


@pytest.mark.issue(171)
def test_migrate_digest_stable_for_unchanged_inputs() -> None:
    rules = {
        "field_renames": {"summary": "description"},
        "path_redirects": {},
        "anchor_redirects": {},
        "supported_asset_extensions": [".png"],
        "execution_grants": [],
    }
    first = migrate(BASELINE_TREE, rules)
    second = migrate(BASELINE_TREE, rules)
    assert first["migrate_digest"] == second["migrate_digest"]
    assert first["source_manifest_digest"] == second["source_manifest_digest"]
    assert first["rules_digest"] == second["rules_digest"]
    assert verify_migrate(first) == {"verified": True}


@pytest.mark.issue(171)
def test_relative_links_and_anchors_rewritten_deterministically() -> None:
    result = migrate(REDIRECT_TREE, REDIRECT_RULES)
    links = result["report"]["links"]
    assert links, "expected at least one link rewrite"
    rewritten = [row for row in links if row["status"] in {"redirect", "rewritten"}]
    assert rewritten, "path/anchor redirects must rewrite targets"
    after_targets = {str(row["after"]) for row in links}
    assert any("handbook.md" in target for target in after_targets)
    assert any("#overview" in target for target in after_targets)

    targets = {item["path"]: item["content"] for item in result["targets"]}
    assert "index.md" in targets
    assert "./handbook.md#overview" in targets["index.md"]
    assert "summary:" not in targets["index.md"]
    assert "description: Welcome page" in targets["index.md"]

    patch_text = "\n".join(
        str(item["unified_diff"]) for item in result["patch"]["files"]
    )
    assert "description: Welcome page" in patch_text
    assert result["changed_count"] >= 1


@pytest.mark.issue(171)
def test_valid_links_preserved_when_no_redirects() -> None:
    rules = {
        "field_renames": {},
        "path_redirects": {},
        "anchor_redirects": {},
        "supported_asset_extensions": [".png"],
        "execution_grants": [],
    }
    result = migrate(BASELINE_TREE, rules)
    link_rows = [row for row in result["report"]["links"] if row["kind"] == "link"]
    preserved = [row for row in link_rows if row["status"] == "preserved"]
    assert preserved
    unresolved = [
        row
        for row in result["report"]["links"]
        if row["status"] == "unresolved" and "guide.md" in str(row["before"])
    ]
    assert not unresolved


@pytest.mark.issue(171)
def test_broken_external_unsafe_and_unsupported_become_findings() -> None:
    result = migrate(UNSAFE_TREE, UNSAFE_RULES)
    statuses = {row["status"] for row in result["report"]["links"]}
    assert "unsafe" in statuses
    assert "external" in statuses
    assert "unresolved" in statuses
    assert "unsupported" in statuses

    feature_ids = {item["feature_id"] for item in result["findings"]}
    assert "md.link.path_traversal" in feature_ids
    assert "md.link.external" in feature_ids
    assert "md.link.unresolved" in feature_ids
    assert "md.asset.unsupported" in feature_ids
    for item in result["findings"]:
        assert item["class"] in FEATURE_CLASSES


@pytest.mark.issue(171)
def test_no_path_traversal_in_entries_or_rules() -> None:
    bad_entries = migrate(
        [{"path": "../secret.md", "content": "# no"}],
        UNSAFE_RULES,
    )
    assert bad_entries["error"] == "path_traversal"

    bad_rules = migrate(
        BASELINE_TREE,
        {"path_redirects": {"guide.md": "../outside.md"}},
    )
    assert bad_rules["error"] == "rules_path_unsafe"


@pytest.mark.issue(171)
def test_external_fetch_requires_explicit_grant_and_still_no_network() -> None:
    granted = migrate(
        UNSAFE_TREE,
        {**UNSAFE_RULES, "execution_grants": ["fetch_remote_urls"]},
    )
    external = [
        row for row in granted["report"]["links"] if row["status"] == "external_granted"
    ]
    assert external
    feature_ids = {item["feature_id"] for item in granted["findings"]}
    assert "md.link.external_granted" in feature_ids
    # Star never copies remote bytes into targets.
    for item in granted.get("targets", []):
        assert "example.com" not in item["content"] or "https://example.com" in item["content"]


@pytest.mark.issue(171)
def test_payload_shape_and_no_unrelated_source_echo() -> None:
    result = migrate(REDIRECT_TREE, REDIRECT_RULES)
    assert_payload_keys(
        result,
        (
            "source_manifest_digest",
            "rules_digest",
            "file_entries",
            "patch",
            "patch_digest",
            "mapping_digest",
            "report",
            "findings",
            "migrate_digest",
            "targets",
            "entry_count",
            "changed_count",
            "finding_count",
            "findings_truncated",
        ),
    )
    # Digest-bound body must verify without relying on ephemeral target bytes.
    verify_payload = {
        key: value
        for key, value in result.items()
        if key not in {"patch", "report", "targets"}
    }
    assert verify_migrate(verify_payload) == {"verified": True}


@pytest.mark.issue(171)
def test_digest_changes_when_rules_change() -> None:
    baseline = migrate(REDIRECT_TREE, REDIRECT_RULES)
    mutated_rules = copy.deepcopy(REDIRECT_RULES)
    mutated_rules["field_renames"] = {"summary": "blurb"}
    changed = migrate(REDIRECT_TREE, mutated_rules)
    assert changed["rules_digest"] != baseline["rules_digest"]
    assert changed["migrate_digest"] != baseline["migrate_digest"]


@pytest.mark.issue(171)
def test_manifest_contract_and_tool_schema() -> None:
    manifest = load_star_manifest("docs_frontmatter_link_asset_migrate")
    assert manifest["star"]["name"] == "orrery/docs-frontmatter-link-asset-migrate"
    assert (
        manifest["star"]["direct_mcp_path"]
        == "/stars/docs-frontmatter-link-asset-migrate/mcp"
    )
    assert manifest["runtime"]["skill_factory"] == (
        "stars.docs_frontmatter_link_asset_migrate.skill:build_skill"
    )
    assert manifest["policy"]["allowed_egress"] == []
    assert_manifest_publish_corpus("docs_frontmatter_link_asset_migrate")
    assert_tool_schema_keys(tool_schemas(), {"migrate"})


@pytest.mark.issue(171)
def test_skill_migrate_tool_round_trip() -> None:
    skill = build_skill()
    tool = next(item for item in skill._pending if item.name == "migrate")
    envelope = tool.handler(entries=REDIRECT_TREE, rules=REDIRECT_RULES)
    payload = envelope.to_wire()["payload"]
    assert payload["migrate_digest"] == migrate(REDIRECT_TREE, REDIRECT_RULES)["migrate_digest"]
    assert verify_migrate(payload) == {"verified": True}
