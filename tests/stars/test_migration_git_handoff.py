"""Tests for orrery/migration-git-handoff — issue #180."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from stars._core.migration_run import (
    MigrationRunStore,
    build_change_bundle,
    build_validation,
    seal_apply,
)
from stars.migration_git_handoff.contract import (
    POLICY_CHECKOUT_ROOTS,
    POLICY_MIGRATION_HANDOFF,
    tool_schemas,
)
from stars.migration_git_handoff.service import (
    handoff,
    migration_handoff_grant_digest,
    repo_policy_digest,
    verify_handoff_receipt,
)
from stars.migration_git_handoff.skill import build_skill
from stars.write_authority_check.contract import POLICY_EXPLICIT_PATHS
from stars.write_authority_check.service import grant_digest
from tests.stars.helpers import (
    assert_manifest_publish_corpus,
    assert_payload_keys,
    assert_tool_schema_keys,
    load_star_manifest,
)
from tests.stars.test_migration_profile import MYST_PROFILE_BASE, _with_digest

_PROFILE_PATH = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "migration"
    / "profiles"
    / "docs_myst_to_mdx_baseline.json"
)
CHECKOUT_ROOT = "workspace/demo-repo"
SOURCE_MANIFEST = "e" * 64


@pytest.fixture
def baseline_profile() -> dict[str, object]:
    return json.loads(_PROFILE_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def myst_profile() -> dict[str, object]:
    return _with_digest(MYST_PROFILE_BASE)


@pytest.fixture
def sealed_bundle() -> dict[str, object]:
    return build_change_bundle(
        plan_digest="1" * 64,
        patch_digest="2" * 64,
        file_entries=[
            {
                "path": "docs/page.md",
                "source_digest": "3" * 64,
                "target_digest": "4" * 64,
            }
        ],
        mapping_digest="5" * 64,
        warnings=[],
    )


@pytest.fixture
def repo_policy() -> dict[str, object]:
    roots = [CHECKOUT_ROOT, "workspace/other"]
    digest = repo_policy_digest(POLICY_CHECKOUT_ROOTS, roots)
    return {
        "policy": POLICY_CHECKOUT_ROOTS,
        "allowed_roots": roots,
        "policy_digest": digest,
    }


@pytest.fixture
def local_validation(
    sealed_bundle: dict[str, object],
    myst_profile: dict[str, object],
) -> dict[str, object]:
    validation = build_validation(
        bundle_digest=str(sealed_bundle["bundle_digest"]),
        validator=dict(myst_profile["validator"]),  # type: ignore[arg-type]
        passed=True,
        findings=[],
        diagnostics_digest="6" * 64,
    )
    return {
        "validation_digest": validation["validation_digest"],
        "passed": True,
        "validator": dict(myst_profile["validator"]),
        "bundle_digest": sealed_bundle["bundle_digest"],
    }


@pytest.fixture
def migration_authority(
    sealed_bundle: dict[str, object],
    myst_profile: dict[str, object],
) -> dict[str, object]:
    grant = migration_handoff_grant_digest(
        bundle_digest=str(sealed_bundle["bundle_digest"]),
        profile_digest=str(myst_profile["profile_digest"]),
        checkout_root=CHECKOUT_ROOT,
    )
    return {
        "policy": POLICY_MIGRATION_HANDOFF,
        "grant_digest": grant,
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }


@pytest.fixture
def path_authority(sealed_bundle: dict[str, object]) -> dict[str, object]:
    paths = ["docs/page.md"]
    return {
        "policy": POLICY_EXPLICIT_PATHS,
        "allowed_paths": paths,
        "grant_digest": grant_digest(POLICY_EXPLICIT_PATHS, paths),
    }


@pytest.fixture
def branch_ref() -> dict[str, object]:
    return {
        "branch": "migration/docs-mdx-safe",
        "title_digest": "7" * 64,
        "body_digest": "8" * 64,
    }


def _handoff_kwargs(
    *,
    myst_profile: dict[str, object],
    sealed_bundle: dict[str, object],
    repo_policy: dict[str, object],
    authority: dict[str, object],
    local_validation: dict[str, object],
    branch_ref: dict[str, object],
    **overrides: object,
) -> dict[str, object]:
    base = {
        "profile": myst_profile,
        "change_bundle": sealed_bundle,
        "repo_identity_policy": repo_policy,
        "checkout_root": CHECKOUT_ROOT,
        "authority": authority,
        "local_validation": local_validation,
        "branch_or_pr_ref": branch_ref,
    }
    base.update(overrides)
    return base


@pytest.mark.issue(180)
def test_success_emits_digest_only_receipt(
    myst_profile: dict[str, object],
    sealed_bundle: dict[str, object],
    repo_policy: dict[str, object],
    migration_authority: dict[str, object],
    local_validation: dict[str, object],
    branch_ref: dict[str, object],
) -> None:
    result = handoff(**_handoff_kwargs(
        myst_profile=myst_profile,
        sealed_bundle=sealed_bundle,
        repo_policy=repo_policy,
        authority=migration_authority,
        local_validation=local_validation,
        branch_ref=branch_ref,
        sealed_validation_digest=local_validation["validation_digest"],
    ))
    assert "error" not in result
    assert result["authorized"] is True
    receipt = result["handoff_receipt"]
    assert isinstance(receipt, dict)
    assert_payload_keys(
        receipt,
        (
            "schema_version",
            "profile_id",
            "profile_digest",
            "repo_identity_policy",
            "checkout_root_digest",
            "bundle_digest",
            "local_validation_digest",
            "branch_or_pr_ref",
            "authority_result",
            "handoff_receipt_digest",
        ),
    )
    assert receipt["bundle_digest"] == sealed_bundle["bundle_digest"]
    assert receipt["local_validation_digest"] == local_validation["validation_digest"]
    assert receipt["branch_or_pr_ref"]["branch"] == branch_ref["branch"]
    assert "token" not in json.dumps(receipt)
    assert "patch_text" not in json.dumps(receipt)
    verified = verify_handoff_receipt(receipt)
    assert verified["verified"] is True


@pytest.mark.issue(180)
def test_rejects_changed_bundle_digest(
    myst_profile: dict[str, object],
    sealed_bundle: dict[str, object],
    repo_policy: dict[str, object],
    migration_authority: dict[str, object],
    local_validation: dict[str, object],
    branch_ref: dict[str, object],
) -> None:
    tampered = copy.deepcopy(sealed_bundle)
    tampered["bundle_digest"] = "f" * 64
    result = handoff(**_handoff_kwargs(
        myst_profile=myst_profile,
        sealed_bundle=tampered,
        repo_policy=repo_policy,
        authority=migration_authority,
        local_validation=local_validation,
        branch_ref=branch_ref,
    ))
    assert result["error"] == "bundle_digest_mismatch"


@pytest.mark.issue(180)
def test_rejects_unsealed_bundle_missing_fields(
    myst_profile: dict[str, object],
    repo_policy: dict[str, object],
    migration_authority: dict[str, object],
    local_validation: dict[str, object],
    branch_ref: dict[str, object],
) -> None:
    result = handoff(**_handoff_kwargs(
        myst_profile=myst_profile,
        sealed_bundle={"bundle_digest": "a" * 64},
        repo_policy=repo_policy,
        authority=migration_authority,
        local_validation=local_validation,
        branch_ref=branch_ref,
    ))
    assert result["error"] == "bundle_unsealed"


@pytest.mark.issue(180)
def test_rejects_unsealed_bundle_with_private_field(
    myst_profile: dict[str, object],
    sealed_bundle: dict[str, object],
    repo_policy: dict[str, object],
    migration_authority: dict[str, object],
    local_validation: dict[str, object],
    branch_ref: dict[str, object],
) -> None:
    leaked = copy.deepcopy(sealed_bundle)
    leaked["patch_text"] = "secret patch body"
    result = handoff(**_handoff_kwargs(
        myst_profile=myst_profile,
        sealed_bundle=leaked,
        repo_policy=repo_policy,
        authority=migration_authority,
        local_validation=local_validation,
        branch_ref=branch_ref,
    ))
    assert result["error"] == "bundle_unsealed"


@pytest.mark.issue(180)
def test_rejects_unauthorized_checkout(
    myst_profile: dict[str, object],
    sealed_bundle: dict[str, object],
    repo_policy: dict[str, object],
    migration_authority: dict[str, object],
    local_validation: dict[str, object],
    branch_ref: dict[str, object],
) -> None:
    result = handoff(**_handoff_kwargs(
        myst_profile=myst_profile,
        sealed_bundle=sealed_bundle,
        repo_policy=repo_policy,
        authority=migration_authority,
        local_validation=local_validation,
        branch_ref=branch_ref,
        checkout_root="workspace/forbidden",
    ))
    assert result["error"] == "checkout_unauthorized"


@pytest.mark.issue(180)
def test_rejects_validation_mismatch(
    myst_profile: dict[str, object],
    sealed_bundle: dict[str, object],
    repo_policy: dict[str, object],
    migration_authority: dict[str, object],
    local_validation: dict[str, object],
    branch_ref: dict[str, object],
) -> None:
    result = handoff(**_handoff_kwargs(
        myst_profile=myst_profile,
        sealed_bundle=sealed_bundle,
        repo_policy=repo_policy,
        authority=migration_authority,
        local_validation=local_validation,
        branch_ref=branch_ref,
        sealed_validation_digest="9" * 64,
    ))
    assert result["error"] == "validation_mismatch"


@pytest.mark.issue(180)
def test_rejects_failed_local_validation(
    myst_profile: dict[str, object],
    sealed_bundle: dict[str, object],
    repo_policy: dict[str, object],
    migration_authority: dict[str, object],
    local_validation: dict[str, object],
    branch_ref: dict[str, object],
) -> None:
    failed = copy.deepcopy(local_validation)
    failed["passed"] = False
    result = handoff(**_handoff_kwargs(
        myst_profile=myst_profile,
        sealed_bundle=sealed_bundle,
        repo_policy=repo_policy,
        authority=migration_authority,
        local_validation=failed,
        branch_ref=branch_ref,
    ))
    assert result["error"] == "validation_mismatch"


@pytest.mark.issue(180)
def test_rejects_expired_authority(
    myst_profile: dict[str, object],
    sealed_bundle: dict[str, object],
    repo_policy: dict[str, object],
    migration_authority: dict[str, object],
    local_validation: dict[str, object],
    branch_ref: dict[str, object],
) -> None:
    expired = copy.deepcopy(migration_authority)
    expired["expires_at"] = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    result = handoff(**_handoff_kwargs(
        myst_profile=myst_profile,
        sealed_bundle=sealed_bundle,
        repo_policy=repo_policy,
        authority=expired,
        local_validation=local_validation,
        branch_ref=branch_ref,
    ))
    assert result["error"] == "authority_expired"


@pytest.mark.issue(180)
def test_explicit_paths_authority_covers_bundle_paths(
    myst_profile: dict[str, object],
    sealed_bundle: dict[str, object],
    repo_policy: dict[str, object],
    path_authority: dict[str, object],
    local_validation: dict[str, object],
    branch_ref: dict[str, object],
) -> None:
    result = handoff(**_handoff_kwargs(
        myst_profile=myst_profile,
        sealed_bundle=sealed_bundle,
        repo_policy=repo_policy,
        authority=path_authority,
        local_validation=local_validation,
        branch_ref=branch_ref,
    ))
    assert "error" not in result
    assert result["authorized"] is True


@pytest.mark.issue(180)
def test_store_sealed_bundle_required_when_missing(
    myst_profile: dict[str, object],
    sealed_bundle: dict[str, object],
    repo_policy: dict[str, object],
    migration_authority: dict[str, object],
    local_validation: dict[str, object],
    branch_ref: dict[str, object],
) -> None:
    store = MigrationRunStore()
    result = handoff(
        **_handoff_kwargs(
            myst_profile=myst_profile,
            sealed_bundle=sealed_bundle,
            repo_policy=repo_policy,
            authority=migration_authority,
            local_validation=local_validation,
            branch_ref=branch_ref,
        ),
        store=store,
        replay_key="a" * 64,
    )
    assert result["error"] == "bundle_unsealed"


@pytest.mark.issue(180)
def test_store_accepts_matching_sealed_bundle(
    myst_profile: dict[str, object],
    sealed_bundle: dict[str, object],
    repo_policy: dict[str, object],
    migration_authority: dict[str, object],
    local_validation: dict[str, object],
    branch_ref: dict[str, object],
) -> None:
    store = MigrationRunStore()
    plan = {
        "plan_digest": sealed_bundle["plan_digest"],
        "profile_digest": myst_profile["profile_digest"],
    }
    sealed = seal_apply(
        store,
        profile=myst_profile,
        source_manifest_digest=SOURCE_MANIFEST,
        plan=plan,
        patch_digest=str(sealed_bundle["patch_digest"]),
        file_entries=list(sealed_bundle["file_entries"]),  # type: ignore[arg-type]
        mapping_digest=str(sealed_bundle["mapping_digest"]),
    )
    assert "error" not in sealed
    replay_key = str(sealed["replay_key"])
    result = handoff(
        **_handoff_kwargs(
            myst_profile=myst_profile,
            sealed_bundle=sealed_bundle,
            repo_policy=repo_policy,
            authority=migration_authority,
            local_validation=local_validation,
            branch_ref=branch_ref,
        ),
        store=store,
        replay_key=replay_key,
    )
    assert "error" not in result
    assert result["authorized"] is True


@pytest.mark.issue(180)
def test_manifest_contract_and_corpus() -> None:
    manifest = load_star_manifest("migration_git_handoff")
    assert manifest["star"]["name"] == "orrery/migration-git-handoff"
    assert manifest["policy"]["allowed_egress"] == []
    assert_tool_schema_keys(tool_schemas(), {"handoff"})
    assert_manifest_publish_corpus("migration_git_handoff")
    assert {item.name for item in build_skill()._pending} == {"handoff"}
    registry = __import__("stars.builtins", fromlist=["builtin_registry"]).builtin_registry()
    definition = next(
        item for item in registry if item.name == "orrery/migration-git-handoff"
    )
    assert definition.direct_mcp_path == "/stars/migration-git-handoff/mcp"


@pytest.mark.issue(180)
def test_skill_handoff_roundtrip(
    myst_profile: dict[str, object],
    sealed_bundle: dict[str, object],
    repo_policy: dict[str, object],
    migration_authority: dict[str, object],
    local_validation: dict[str, object],
    branch_ref: dict[str, object],
) -> None:
    skill = build_skill()
    envelope = next(item for item in skill._pending if item.name == "handoff").handler(
        profile=myst_profile,
        change_bundle=sealed_bundle,
        repo_identity_policy=repo_policy,
        checkout_root=CHECKOUT_ROOT,
        authority=migration_authority,
        local_validation=local_validation,
        branch_or_pr_ref=branch_ref,
    )
    assert envelope.payload["authorized"] is True
    assert "handoff_receipt" in envelope.payload
