"""Tests for orrery/api-spec-openapi-inventory — ADR 0008 analyze inventory (#174)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from stars.api_spec_openapi_inventory.contract import FEATURE_CLASSES, tool_schemas
from stars.api_spec_openapi_inventory.fixtures import (
    BASELINE_SPEC,
    COMPATIBLE_MINIMAL,
    EXTERNAL_REF_SPEC,
    MALFORMED_SPEC,
)
from stars.api_spec_openapi_inventory.service import inventory, verify_inventory
from stars.api_spec_openapi_inventory.skill import build_skill
from tests.stars.helpers import (
    assert_manifest_publish_corpus,
    assert_payload_keys,
    assert_tool_schema_keys,
    load_star_manifest,
)

_CORPUS_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "migration" / "cases"


def _corpus_entry(case_id: str) -> list[dict[str, str]]:
    path = _CORPUS_ROOT / case_id / "source" / "openapi.json"
    return [{"path": "openapi.json", "content": path.read_text(encoding="utf-8")}]


@pytest.mark.issue(174)
def test_inventory_digest_stable_for_unchanged_spec() -> None:
    first = inventory(BASELINE_SPEC)
    second = inventory(BASELINE_SPEC)
    assert first["inventory_digest"] == second["inventory_digest"]
    assert first["source_manifest_digest"] == second["source_manifest_digest"]
    assert verify_inventory(first) == {"verified": True}


@pytest.mark.issue(174)
def test_inventory_digest_changes_when_spec_changes() -> None:
    baseline = inventory(BASELINE_SPEC)
    mutated = copy.deepcopy(BASELINE_SPEC)
    mutated[0] = {
        **mutated[0],
        "content": mutated[0]["content"].replace("Demo", "Demo Two"),
    }
    changed = inventory(mutated)
    assert changed["inventory_digest"] != baseline["inventory_digest"]
    assert changed["source_manifest_digest"] != baseline["source_manifest_digest"]


@pytest.mark.issue(174)
def test_identifies_dialect_and_profile_relevant_constructs() -> None:
    result = inventory(BASELINE_SPEC)
    assert result["source"] == {"kind": "openapi", "version": "3.0.3"}
    findings = result["findings"]
    feature_ids = {item["feature_id"] for item in findings}
    classes = {item["class"] for item in findings}

    assert "openapi.version" in feature_ids
    assert "openapi.json_schema.draft2020" in feature_ids
    assert "openapi.operation" in feature_ids
    assert "openapi.schema" in feature_ids
    assert "openapi.security_scheme" in feature_ids
    assert "openapi.webhook" in feature_ids
    assert "openapi.discriminator" in feature_ids
    assert "openapi.discriminator.mapping" in feature_ids
    assert "openapi.nullable" in feature_ids
    assert "openapi.format" in feature_ids
    assert "openapi.example" in feature_ids
    assert "openapi.extension.vendor" in feature_ids
    assert "openapi.ref.internal" in feature_ids

    assert "safe" in classes
    assert "transformable" in classes
    assert "decision_required" in classes
    assert "unsupported" in classes

    draft = [
        item
        for item in findings
        if item["feature_id"] == "openapi.json_schema.draft2020"
    ]
    assert draft and draft[0]["class"] == "transformable"
    assert "semantic upgrade" not in json.dumps(result).lower()


@pytest.mark.issue(174)
def test_external_ref_requires_scoped_policy_and_never_fetches() -> None:
    denied = inventory(EXTERNAL_REF_SPEC)
    external = [
        item for item in denied["findings"] if item["feature_id"] == "openapi.ref.external"
    ]
    assert external
    assert external[0]["class"] == "decision_required"
    assert "not fetched" in external[0]["message"] or "denied" in external[0]["message"]

    allowed = inventory(
        EXTERNAL_REF_SPEC,
        ref_policy={
            "mode": "allow_prefixes",
            "allowed_prefixes": ["https://example.com/"],
        },
    )
    scoped = [
        item for item in allowed["findings"] if item["feature_id"] == "openapi.ref.external"
    ]
    assert scoped
    assert scoped[0]["class"] == "decision_required"
    assert "not fetched" in scoped[0]["message"]

    out_of_scope = inventory(
        EXTERNAL_REF_SPEC,
        ref_policy={
            "mode": "allow_prefixes",
            "allowed_prefixes": ["https://other.example/"],
        },
    )
    blocked = [
        item
        for item in out_of_scope["findings"]
        if item["feature_id"] == "openapi.ref.external"
    ]
    assert blocked and blocked[0]["class"] == "unsupported"


@pytest.mark.issue(174)
def test_malformed_and_corpus_compatible_cases() -> None:
    malformed = inventory(MALFORMED_SPEC)
    assert any(item["class"] == "malformed" for item in malformed["findings"])

    compatible = inventory(COMPATIBLE_MINIMAL)
    assert compatible["source"]["version"] == "3.0.3"
    assert any(
        item["feature_id"] == "openapi.json_schema.draft2020"
        for item in compatible["findings"]
    )

    corpus_safe = inventory(_corpus_entry("openapi_safe_schema_upgrade"))
    assert any(
        item["feature_id"] == "openapi.json_schema.draft2020"
        and item["class"] == "transformable"
        for item in corpus_safe["findings"]
    )

    corpus_disc = inventory(_corpus_entry("openapi_unsupported_discriminator"))
    assert any(
        item["feature_id"] == "openapi.discriminator.mapping"
        and item["class"] == "unsupported"
        for item in corpus_disc["findings"]
    )

    corpus_bad = inventory(_corpus_entry("openapi_malformed_spec"))
    assert any(item["class"] == "malformed" for item in corpus_bad["findings"])


@pytest.mark.issue(174)
def test_findings_use_adr_0008_feature_classes_only() -> None:
    combined = (
        inventory(BASELINE_SPEC)["findings"]
        + inventory(MALFORMED_SPEC)["findings"]
        + inventory(EXTERNAL_REF_SPEC)["findings"]
    )
    for item in combined:
        assert item["class"] in FEATURE_CLASSES


@pytest.mark.issue(174)
def test_inventory_payload_shape_and_no_raw_content_echo() -> None:
    result = inventory(BASELINE_SPEC)
    assert_payload_keys(
        result,
        (
            "source",
            "source_manifest_digest",
            "findings",
            "inventory_digest",
            "analysis_digest",
            "entry_count",
            "finding_count",
            "findings_truncated",
            "ref_policy",
        ),
    )
    serialized = str(result)
    for entry in BASELINE_SPEC:
        assert entry["content"] not in serialized


@pytest.mark.issue(174)
def test_manifest_contract_and_tool_schema() -> None:
    manifest = load_star_manifest("api_spec_openapi_inventory")
    assert manifest["star"]["name"] == "orrery/api-spec-openapi-inventory"
    assert (
        manifest["star"]["direct_mcp_path"] == "/stars/api-spec-openapi-inventory/mcp"
    )
    assert manifest["runtime"]["skill_factory"] == (
        "stars.api_spec_openapi_inventory.skill:build_skill"
    )
    assert_manifest_publish_corpus("api_spec_openapi_inventory")
    assert_tool_schema_keys(tool_schemas(), {"inventory"})


@pytest.mark.issue(174)
def test_skill_inventory_tool_round_trip() -> None:
    skill = build_skill()
    tool = next(item for item in skill._pending if item.name == "inventory")
    envelope = tool.handler(entries=BASELINE_SPEC)
    payload = envelope.to_wire()["payload"]
    assert payload["inventory_digest"] == inventory(BASELINE_SPEC)["inventory_digest"]
    assert verify_inventory(payload) == {"verified": True}
