"""Tests for orrery/api-spec-openapi-validate — ADR 0008 validate stage (#177)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from stars._core.migration_run import MigrationRunStore, build_change_bundle
from stars.api_spec_openapi_upgrade_safe.service import apply, plan
from stars.api_spec_openapi_validate.contract import tool_schemas
from stars.api_spec_openapi_validate.fixtures import (
    MALFORMED_TARGET,
    POLICY_BLOCK_PLAN,
    SAFE_SOURCE,
    VALID_TARGET,
)
from stars.api_spec_openapi_validate.service import validate
from stars.api_spec_openapi_validate.skill import build_skill
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
_CORPUS_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "migration" / "cases"

_GOLDEN_CASES = (
    "openapi_malformed_spec",
    "openapi_validator_failure",
    "openapi_safe_schema_upgrade",
)


@pytest.fixture
def pinned_profile() -> dict[str, object]:
    return json.loads(_PROFILE_PATH.read_text(encoding="utf-8"))


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


def _load_corpus_case(case_id: str) -> dict[str, object]:
    case_dir = _CORPUS_ROOT / case_id
    source_path = case_dir / "source" / "openapi.json"
    return {
        "source": [{"path": "openapi.json", "content": source_path.read_text(encoding="utf-8")}],
        "bundle": json.loads((case_dir / "stages/bundle.json").read_text(encoding="utf-8")),
        "plan": json.loads((case_dir / "stages/plan.json").read_text(encoding="utf-8")),
        "golden_validation": json.loads(
            (case_dir / "stages/validation.json").read_text(encoding="utf-8")
        ),
    }


def _targets_for_case(case_id: str, profile: dict[str, object]) -> list[dict[str, str]]:
    case = _load_corpus_case(case_id)
    source = case["source"]
    assert isinstance(source, list)
    planned = plan(source, profile)
    assert "error" not in planned
    applied = apply(source, planned, profile)
    assert "error" not in applied
    targets = applied["targets"]
    assert isinstance(targets, list)
    return targets


@pytest.mark.issue(177)
def test_malformed_target_fails_deterministically(
    pinned_profile: dict[str, object],
) -> None:
    bundle = _bundle_for_paths(["openapi.json"])
    result = validate(MALFORMED_TARGET, bundle, pinned_profile)
    assert "error" not in result
    assert result["validation_passed"] is False
    assert result["validation"]["passed"] is False
    malformed = [
        item
        for item in result["findings"]
        if item.get("feature_id") == "openapi.json_schema.draft2020"
    ]
    assert malformed
    assert malformed[0]["class"] == "malformed"
    assert malformed[0]["message"] == "json parse error"
    assert MALFORMED_TARGET[0]["content"] not in str(result["diagnostics"])


@pytest.mark.issue(177)
def test_validator_identity_in_validation_receipt(
    pinned_profile: dict[str, object],
) -> None:
    bundle = _bundle_for_paths(["openapi.json"])
    result = validate(VALID_TARGET, bundle, pinned_profile)
    assert "error" not in result
    assert result["validator"]["name"] == "orrery/openapi-validate"
    assert result["validator"]["version"] == "1.0.0"
    assert result["validation"]["validator"]["name"] == "orrery/openapi-validate"
    assert result["validation"]["validator"]["version"] == "1.0.0"
    assert result["validation"]["validator"]["digest"] == pinned_profile["validator"]["digest"]


@pytest.mark.issue(177)
def test_diagnostics_redacted_and_bounded(
    pinned_profile: dict[str, object],
) -> None:
    bundle = _bundle_for_paths(["openapi.json"])
    result = validate(MALFORMED_TARGET, bundle, pinned_profile)
    assert "error" not in result
    diagnostics = result["diagnostics"]
    assert "source_bytes" not in str(diagnostics)
    assert "target_bytes" not in str(diagnostics)
    assert MALFORMED_TARGET[0]["content"] not in str(diagnostics)
    assert len(result["diagnostics_digest"]) == 64


@pytest.mark.issue(177)
def test_policy_blocked_plan_fails_closed(
    pinned_profile: dict[str, object],
) -> None:
    plan_body = copy.deepcopy(POLICY_BLOCK_PLAN)
    plan_body["profile_digest"] = pinned_profile["profile_digest"]
    bundle = _bundle_for_paths(["openapi.json"], plan_digest=str(plan_body["plan_digest"]))
    result = validate(
        VALID_TARGET,
        bundle,
        pinned_profile,
        plan=plan_body,
    )
    assert "error" not in result
    assert result["validation_passed"] is False
    blocked = [item for item in result["findings"] if item.get("id") == "breaking.path.remove"]
    assert blocked
    assert blocked[0]["severity"] == "breaking"
    assert blocked[0]["action"] == "block"


@pytest.mark.issue(177)
def test_failed_validation_cannot_be_overwritten_as_success(
    pinned_profile: dict[str, object],
) -> None:
    bundle = _bundle_for_paths(["openapi.json"])
    store = MigrationRunStore()
    failed = validate(MALFORMED_TARGET, bundle, pinned_profile, store=store)
    assert failed["validation_passed"] is False
    replay_key = failed["sealed_stage"]["replay_key"]

    success_attempt = validate(VALID_TARGET, bundle, pinned_profile, store=store)
    assert success_attempt["validation_passed"] is True
    assert success_attempt.get("error") == "replay_incompatible" or (
        success_attempt.get("sealed_stage", {}).get("reused") is True
        and store.get(replay_key, "validate")["passed"] is False
    )


@pytest.mark.issue(177)
@pytest.mark.parametrize("case_id", _GOLDEN_CASES)
def test_golden_corpus_cases_match_validation_findings(
    pinned_profile: dict[str, object], case_id: str
) -> None:
    case = _load_corpus_case(case_id)
    source = case["source"]
    bundle = case["bundle"]
    plan_payload = case["plan"]
    golden = case["golden_validation"]
    assert isinstance(source, list)
    assert isinstance(bundle, dict)
    assert isinstance(plan_payload, dict)
    assert isinstance(golden, dict)

    targets = _targets_for_case(case_id, pinned_profile)
    result = validate(
        targets,
        bundle,
        pinned_profile,
        source_entries=source,
        plan=plan_payload,
    )
    assert "error" not in result
    validation = result["validation"]
    assert validation["passed"] == golden["passed"]
    assert validation["validator"] == golden["validator"]
    assert validation["bundle_digest"] == golden["bundle_digest"]
    assert validation["findings"] == golden["findings"]
    assert result["validation_passed"] is golden["passed"]
    assert_payload_keys(
        validation,
        (
            "bundle_digest",
            "validator",
            "passed",
            "findings",
            "diagnostics_digest",
            "validation_digest",
        ),
    )


@pytest.mark.issue(177)
def test_rejects_tampered_bundle(pinned_profile: dict[str, object]) -> None:
    bundle = _bundle_for_paths(["openapi.json"])
    tampered = copy.deepcopy(bundle)
    tampered["bundle_digest"] = "f" * 64
    rejected = validate(VALID_TARGET, tampered, pinned_profile)
    assert rejected["error"] == "bundle_digest_mismatch"


@pytest.mark.issue(177)
def test_manifest_contract_and_tool_schema() -> None:
    manifest = load_star_manifest("api_spec_openapi_validate")
    assert manifest["star"]["name"] == "orrery/api-spec-openapi-validate"
    assert manifest["star"]["direct_mcp_path"] == "/stars/api-spec-openapi-validate/mcp"
    assert manifest["runtime"]["skill_factory"] == (
        "stars.api_spec_openapi_validate.skill:build_skill"
    )
    assert_manifest_publish_corpus("api_spec_openapi_validate")
    assert_tool_schema_keys(tool_schemas(), {"validate"})


@pytest.mark.issue(177)
def test_skill_validate_round_trip(pinned_profile: dict[str, object]) -> None:
    planned = plan(SAFE_SOURCE, pinned_profile)
    assert "error" not in planned
    applied = apply(SAFE_SOURCE, planned, pinned_profile)
    assert "error" not in applied
    skill = build_skill()
    pending = {item.name: item for item in skill._pending}
    envelope = pending["validate"].handler(
        target_entries=applied["targets"],
        change_bundle=applied["change_bundle"],
        profile=pinned_profile,
        source_entries=SAFE_SOURCE,
        plan=planned,
    )
    payload = envelope.to_wire()["payload"]
    direct = validate(
        applied["targets"],
        applied["change_bundle"],
        pinned_profile,
        source_entries=SAFE_SOURCE,
        plan=planned,
    )
    assert payload["validation_digest"] == direct["validation_digest"]
    assert payload["validation_passed"] is True
