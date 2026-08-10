"""Tests for orrery/api-spec-openapi-upgrade-safe — ADR 0008 plan/apply (#175)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from stars.api_spec_openapi_upgrade_safe.contract import CORPUS_FEATURES, tool_schemas
from stars.api_spec_openapi_upgrade_safe.fixtures import (
    EXTENSION_SPEC,
    MALFORMED_SPEC,
    SAFE_SPEC,
    UNSUPPORTED_SPEC,
)
from stars.api_spec_openapi_upgrade_safe.service import apply, plan
from stars.api_spec_openapi_upgrade_safe.skill import build_skill
from stars.api_spec_openapi_upgrade_safe.transform import target_openapi_parseable
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
    / "api_spec_openapi_3_0_to_3_1_safe.json"
)


@pytest.fixture
def pinned_profile() -> dict[str, object]:
    return json.loads(_PROFILE_PATH.read_text(encoding="utf-8"))


@pytest.mark.issue(175)
def test_safe_fixtures_parse_under_target_validators(
    pinned_profile: dict[str, object],
) -> None:
    planned = plan(SAFE_SPEC, pinned_profile)
    assert "error" not in planned
    assert any(op["op"] == "bump_openapi" for op in planned["planned_ops"])
    assert any(op["op"] == "transform_nullable" for op in planned["planned_ops"])
    bump = next(op for op in planned["planned_ops"] if op["op"] == "bump_openapi")
    assert bump["from"] == "3.0.3"
    assert bump["to"] == "3.1.0"

    result = apply(SAFE_SPEC, planned, pinned_profile)
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
    upgraded = json.loads(targets["openapi.json"])
    assert upgraded["openapi"] == "3.1.0"
    pet = upgraded["components"]["schemas"]["Pet"]
    assert "nullable" not in pet
    assert pet["type"] == ["object", "null"]

    # File mapping preserved (same relative paths).
    assert {item["path"] for item in bundle["file_entries"]} == {"openapi.json"}
    for entry in bundle["file_entries"]:
        assert entry["source_digest"] and entry["target_digest"]
        assert entry["source_digest"] != entry["target_digest"]

    validation = result["baseline_validation"]
    assert validation["passed"] is True
    assert target_openapi_parseable(result["targets"])["passed"] is True


@pytest.mark.issue(175)
def test_unsupported_semantics_cannot_silently_pass_as_equivalent(
    pinned_profile: dict[str, object],
) -> None:
    planned = plan(UNSUPPORTED_SPEC, pinned_profile)
    assert "error" not in planned
    findings = planned["findings"]
    feature_ids = {item["feature_id"] for item in findings}
    classes = {item["class"] for item in findings}

    assert "openapi.discriminator.mapping" in feature_ids
    assert "unsupported" in classes

    hold_ops = [op for op in planned["planned_ops"] if op["op"] == "hold"]
    assert hold_ops, "unsupported constructs must produce hold ops"
    assert any(
        op.get("feature_id") == "openapi.discriminator.mapping" for op in hold_ops
    )

    result = apply(UNSUPPORTED_SPEC, planned, pinned_profile)
    assert "error" not in result
    targets = {item["path"]: item["content"] for item in result["targets"]}

    # Original unsupported mapping preserved — not silently rewritten.
    assert '"mapping"' in targets["openapi.json"]
    assert "#/components/schemas/Cat" in targets["openapi.json"]
    assert targets["openapi.json"] == UNSUPPORTED_SPEC[0]["content"]

    for entry in result["change_bundle"]["file_entries"]:
        assert entry["source_digest"] == entry["target_digest"]


@pytest.mark.issue(175)
def test_extensions_require_explicit_policy_decision(
    pinned_profile: dict[str, object],
) -> None:
    planned = plan(EXTENSION_SPEC, pinned_profile)
    assert "error" not in planned
    feature_ids = {item["feature_id"] for item in planned["findings"]}
    assert "openapi.extension.vendor" in feature_ids
    hold_ops = [
        op
        for op in planned["planned_ops"]
        if op["op"] == "hold" and op.get("feature_id") == "openapi.extension.vendor"
    ]
    assert hold_ops

    result = apply(EXTENSION_SPEC, planned, pinned_profile)
    assert "error" not in result
    assert "x-internal-id" in result["targets"][0]["content"]
    assert result["targets"][0]["content"] == EXTENSION_SPEC[0]["content"]


@pytest.mark.issue(175)
def test_malformed_findings_hold_without_silent_repair(
    pinned_profile: dict[str, object],
) -> None:
    planned = plan(MALFORMED_SPEC, pinned_profile)
    malformed = [item for item in planned["findings"] if item["class"] == "malformed"]
    assert malformed
    result = apply(MALFORMED_SPEC, planned, pinned_profile)
    assert "error" not in result
    assert result["targets"][0]["content"] == MALFORMED_SPEC[0]["content"]


@pytest.mark.issue(175)
def test_apply_idempotent_and_rejects_digest_mismatch(
    pinned_profile: dict[str, object],
) -> None:
    planned = plan(SAFE_SPEC, pinned_profile)
    first = apply(SAFE_SPEC, planned, pinned_profile)
    second = apply(SAFE_SPEC, planned, pinned_profile)
    assert first["bundle_digest"] == second["bundle_digest"]
    assert first["change_bundle"] == second["change_bundle"]

    mutated = copy.deepcopy(SAFE_SPEC)
    mutated[0] = {
        **mutated[0],
        "content": mutated[0]["content"].replace("Demo", "Demo Two"),
    }
    rejected_source = apply(mutated, planned, pinned_profile)
    assert rejected_source["error"] == "source_digest_mismatch"

    other_profile = copy.deepcopy(pinned_profile)
    other_profile["profile_digest"] = "c" * 64
    rejected_profile = apply(SAFE_SPEC, planned, other_profile)
    assert rejected_profile["error"] in {"profile_invalid", "profile_digest_mismatch"}


@pytest.mark.issue(175)
def test_rejects_floating_latest_profile(
    pinned_profile: dict[str, object],
) -> None:
    floating = copy.deepcopy(pinned_profile)
    floating["target"] = {"kind": "openapi", "version": "latest"}
    # Digest will not match; require_profile rejects floating pins.
    rejected = plan(SAFE_SPEC, floating)
    assert rejected["error"] == "profile_invalid"


@pytest.mark.issue(175)
def test_plan_findings_use_adr_classes_only(
    pinned_profile: dict[str, object],
) -> None:
    combined = [
        {**SAFE_SPEC[0], "path": "safe.json"},
        {**UNSUPPORTED_SPEC[0], "path": "unsupported.json"},
        {**EXTENSION_SPEC[0], "path": "extension.json"},
        {**MALFORMED_SPEC[0], "path": "malformed.json"},
    ]
    planned = plan(combined, pinned_profile)
    assert "error" not in planned
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


@pytest.mark.issue(175)
def test_manifest_contract_and_tool_schema() -> None:
    manifest = load_star_manifest("api_spec_openapi_upgrade_safe")
    assert manifest["star"]["name"] == "orrery/api-spec-openapi-upgrade-safe"
    assert (
        manifest["star"]["direct_mcp_path"] == "/stars/api-spec-openapi-upgrade-safe/mcp"
    )
    assert manifest["runtime"]["skill_factory"] == (
        "stars.api_spec_openapi_upgrade_safe.skill:build_skill"
    )
    assert_manifest_publish_corpus("api_spec_openapi_upgrade_safe")
    assert_tool_schema_keys(tool_schemas(), {"plan", "apply"})


@pytest.mark.issue(175)
def test_skill_plan_apply_round_trip(pinned_profile: dict[str, object]) -> None:
    skill = build_skill()
    pending = {item.name: item for item in skill._pending}
    plan_envelope = pending["plan"].handler(entries=SAFE_SPEC, profile=pinned_profile)
    plan_payload = plan_envelope.to_wire()["payload"]
    assert plan_payload["plan_digest"] == plan(SAFE_SPEC, pinned_profile)["plan_digest"]

    apply_envelope = pending["apply"].handler(
        entries=SAFE_SPEC,
        plan=plan_payload,
        profile=pinned_profile,
    )
    apply_payload = apply_envelope.to_wire()["payload"]
    assert apply_payload["bundle_digest"] == apply(SAFE_SPEC, plan_payload, pinned_profile)[
        "bundle_digest"
    ]
    assert apply_payload["baseline_validation"]["passed"] is True
