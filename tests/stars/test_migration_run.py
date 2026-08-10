"""Tests for migration stage persistence (ADR 0008) - issue #166."""

from __future__ import annotations

import pytest

from stars._core.migration_profile import compute_profile_digest
from stars._core.migration_run import (
    MigrationRunError,
    MigrationRunStore,
    assert_no_private_bytes,
    build_analysis,
    build_receipt_fields,
    build_status_payload,
    compute_replay_key,
    run_stage,
    seal_analyze,
    seal_apply,
    seal_plan,
)
from tests.stars.test_migration_profile import MYST_PROFILE_BASE, _with_digest

SOURCE_MANIFEST_DIGEST = "e" * 64


@pytest.fixture
def myst_profile() -> dict[str, object]:
    return _with_digest(MYST_PROFILE_BASE)


@pytest.fixture
def store() -> MigrationRunStore:
    return MigrationRunStore()


@pytest.fixture
def sample_findings() -> list[dict[str, str]]:
    return [
        {
            "feature_id": "myst.directive.include",
            "class": "decision_required",
            "path": "docs/page.md",
        }
    ]


@pytest.mark.issue(166)
def test_compatible_rerun_reuses_sealed_analyze_output(
    store: MigrationRunStore,
    myst_profile: dict[str, object],
    sample_findings: list[dict[str, str]],
) -> None:
    first = seal_analyze(
        store,
        profile=myst_profile,
        source_manifest_digest=SOURCE_MANIFEST_DIGEST,
        findings=sample_findings,
    )
    assert first["reused"] is False
    second = seal_analyze(
        store,
        profile=myst_profile,
        source_manifest_digest=SOURCE_MANIFEST_DIGEST,
        findings=sample_findings,
    )
    assert second["reused"] is True
    assert second["output"] == first["output"]
    assert second["replay_key"] == first["replay_key"]


@pytest.mark.issue(166)
def test_incompatible_replay_is_rejected(
    store: MigrationRunStore,
    myst_profile: dict[str, object],
    sample_findings: list[dict[str, str]],
) -> None:
    first = seal_analyze(
        store,
        profile=myst_profile,
        source_manifest_digest=SOURCE_MANIFEST_DIGEST,
        findings=sample_findings,
    )
    replay_key = first["replay_key"]
    different_findings = [
        {
            "feature_id": "md.heading",
            "class": "safe",
            "path": "docs/other.md",
        }
    ]
    with pytest.raises(MigrationRunError, match="replay_incompatible"):
        store.seal(
            replay_key,
            "analyze",
            build_analysis(
                source_manifest_digest=SOURCE_MANIFEST_DIGEST,
                findings=different_findings,
            ),
        )


@pytest.mark.issue(166)
def test_replay_input_mismatch_when_source_changes(
    store: MigrationRunStore,
    myst_profile: dict[str, object],
    sample_findings: list[dict[str, str]],
) -> None:
    first = seal_analyze(
        store,
        profile=myst_profile,
        source_manifest_digest=SOURCE_MANIFEST_DIGEST,
        findings=sample_findings,
    )
    result = run_stage(
        store,
        profile=myst_profile,
        source_manifest_digest="f" * 64,
        mode="analyze",
        producer=lambda: first["output"],
        replay_key=first["replay_key"],
    )
    assert result["error"] == "replay_input_mismatch"


@pytest.mark.issue(166)
def test_apply_only_consumes_exact_plan_digest(
    store: MigrationRunStore,
    myst_profile: dict[str, object],
    sample_findings: list[dict[str, str]],
) -> None:
    analysis = seal_analyze(
        store,
        profile=myst_profile,
        source_manifest_digest=SOURCE_MANIFEST_DIGEST,
        findings=sample_findings,
    )["output"]
    plan = seal_plan(
        store,
        profile=myst_profile,
        source_manifest_digest=SOURCE_MANIFEST_DIGEST,
        analysis=analysis,
        planned_ops=[{"op": "transform", "path": "docs/page.md"}],
    )["output"]

    ok = seal_apply(
        store,
        profile=myst_profile,
        source_manifest_digest=SOURCE_MANIFEST_DIGEST,
        plan=plan,
        patch_digest="1" * 64,
        file_entries=[
            {"path": "docs/page.md", "source_digest": "2" * 64, "target_digest": "3" * 64}
        ],
        mapping_digest="4" * 64,
    )
    assert "error" not in ok
    assert ok["output"]["plan_digest"] == plan["plan_digest"]

    wrong = seal_apply(
        store,
        profile=myst_profile,
        source_manifest_digest=SOURCE_MANIFEST_DIGEST,
        plan=plan,
        plan_digest="0" * 64,
        patch_digest="1" * 64,
        file_entries=[
            {"path": "docs/page.md", "source_digest": "2" * 64, "target_digest": "3" * 64}
        ],
        mapping_digest="4" * 64,
    )
    assert wrong["error"] == "plan_digest_mismatch"


@pytest.mark.issue(166)
def test_status_and_receipt_payloads_omit_private_source_bytes(
    myst_profile: dict[str, object],
    sample_findings: list[dict[str, str]],
) -> None:
    analysis = build_analysis(
        source_manifest_digest=SOURCE_MANIFEST_DIGEST,
        findings=sample_findings,
    )
    replay_key = compute_replay_key(
        source_manifest_digest=SOURCE_MANIFEST_DIGEST,
        profile_digest=str(myst_profile["profile_digest"]),
        mode="analyze",
        policy_id="docs-mdx-baseline-v1",
    )
    stage_outputs = {"analyze": analysis}
    status = build_status_payload(
        myst_profile,
        mode="analyze",
        replay_key=replay_key,
        source_manifest_digest=SOURCE_MANIFEST_DIGEST,
        stage_outputs=stage_outputs,
        extra={
            "source_bytes": b"secret",
            "full_patch_text": "diff --git a/private",
            "safe_note": "ok",
        },
    )
    receipt = build_receipt_fields(
        myst_profile,
        mode="analyze",
        replay_key=replay_key,
        source_manifest_digest=SOURCE_MANIFEST_DIGEST,
        stage_outputs=stage_outputs,
    )
    for payload in (status, receipt):
        assert "source_bytes" not in payload
        assert "full_patch_text" not in payload
        assert "target_bytes" not in payload
        assert "private_paths" not in payload
        assert_no_private_bytes(payload)
    assert status["analysis_digest"] == analysis["analysis_digest"]
    assert receipt["profile_digest"] == myst_profile["profile_digest"]


@pytest.mark.issue(166)
def test_replay_key_changes_when_profile_digest_changes(
    myst_profile: dict[str, object],
) -> None:
    other = dict(myst_profile)
    other["version"] = "1.0.1"
    other["profile_digest"] = compute_profile_digest(other)
    base_key = compute_replay_key(
        source_manifest_digest=SOURCE_MANIFEST_DIGEST,
        profile_digest=str(myst_profile["profile_digest"]),
        mode="plan",
        policy_id="docs-mdx-baseline-v1",
    )
    changed_key = compute_replay_key(
        source_manifest_digest=SOURCE_MANIFEST_DIGEST,
        profile_digest=str(other["profile_digest"]),
        mode="plan",
        policy_id="docs-mdx-baseline-v1",
    )
    assert base_key != changed_key
