"""Tests for portable migration receipts (ADR 0008 §12) — issue #167."""

from __future__ import annotations

import pytest

from stars._core.migration_receipt import (
    compute_receipt_digest,
    seal_migration_receipt,
    verify_migration_receipt,
)
from stars._core.migration_run import (
    build_analysis,
    build_change_bundle,
    build_plan,
    build_validation,
)
from stars._core.migration_validate import validate_change_bundle
from tests.stars.test_migration_profile import MYST_PROFILE_BASE, _with_digest

SOURCE_MANIFEST_DIGEST = "e" * 64


@pytest.fixture
def myst_profile() -> dict[str, object]:
    return _with_digest(MYST_PROFILE_BASE)


@pytest.fixture
def stage_chain(myst_profile: dict[str, object]) -> dict[str, dict[str, object]]:
    analysis = build_analysis(
        source_manifest_digest=SOURCE_MANIFEST_DIGEST,
        findings=[
            {
                "feature_id": "myst.directive.include",
                "class": "decision_required",
                "path": "docs/page.md",
            }
        ],
    )
    plan = build_plan(
        analysis_digest=str(analysis["analysis_digest"]),
        profile_digest=str(myst_profile["profile_digest"]),
        policy_id="docs-mdx-baseline-v1",
        planned_ops=[{"op": "transform", "path": "docs/page.md"}],
    )
    bundle = build_change_bundle(
        plan_digest=str(plan["plan_digest"]),
        patch_digest="2" * 64,
        file_entries=[
            {
                "path": "docs/page.md",
                "source_digest": "3" * 64,
                "target_digest": "4" * 64,
            }
        ],
        mapping_digest="5" * 64,
    )
    return {"analyze": analysis, "plan": plan, "apply": bundle}


@pytest.mark.issue(167)
def test_cannot_seal_success_when_validator_fails(
    myst_profile: dict[str, object],
    stage_chain: dict[str, dict[str, object]],
) -> None:
    adapter = validate_change_bundle(
        myst_profile,
        stage_chain["apply"],
        checker_passed=False,
        findings=[{"feature_id": "mdx.parse", "class": "malformed", "path": "x.mdx"}],
    )
    validation = adapter["validation"]
    stages = {**stage_chain, "validate": validation}

    refused = seal_migration_receipt(
        myst_profile,
        mode="validate",
        source_manifest_digest=SOURCE_MANIFEST_DIGEST,
        stage_outputs=stages,
        validation=validation,
        require_success=True,
    )
    assert refused["error"] == "cannot_seal_success"
    assert refused["validation_passed"] is False

    failure_receipt = seal_migration_receipt(
        myst_profile,
        mode="validate",
        source_manifest_digest=SOURCE_MANIFEST_DIGEST,
        stage_outputs=stages,
        validation=validation,
        require_success=False,
    )
    assert "error" not in failure_receipt
    assert failure_receipt["receipt"]["validation_passed"] is False
    assert failure_receipt["validation_passed"] is False


@pytest.mark.issue(167)
def test_independent_verify_recovers_identity_pins(
    myst_profile: dict[str, object],
    stage_chain: dict[str, dict[str, object]],
) -> None:
    adapter = validate_change_bundle(
        myst_profile,
        stage_chain["apply"],
        checker_passed=True,
        findings=[{"feature_id": "md.heading", "class": "safe", "path": "docs/page.md"}],
    )
    validation = adapter["validation"]
    stages = {**stage_chain, "validate": validation}
    sealed = seal_migration_receipt(
        myst_profile,
        mode="validate",
        source_manifest_digest=SOURCE_MANIFEST_DIGEST,
        stage_outputs=stages,
        validation=validation,
        require_success=True,
    )
    receipt = sealed["receipt"]
    assert receipt["validation_passed"] is True
    assert receipt["receipt_digest"] == compute_receipt_digest(receipt)
    assert "source_bytes" not in receipt
    assert "full_patch_text" not in receipt

    verified = verify_migration_receipt(
        receipt,
        profile=myst_profile,
        validation=validation,
        stage_artifacts=stages,
    )
    assert verified["verified"] is True
    recovered = verified["recovered"]
    assert recovered["profile_id"] == myst_profile["profile_id"]
    assert recovered["profile_version"] == myst_profile["version"]
    assert recovered["profile_digest"] == myst_profile["profile_digest"]
    assert recovered["target"] == {"kind": "mdx", "version": "3.0.0"}
    assert recovered["transformer"] == {
        "name": "orrery/docs-myst-to-mdx",
        "version": "1.0.0",
        "digest": "a" * 64,
    }
    assert recovered["validator"] == {
        "name": "orrery/docs-mdx-validate",
        "version": "1.0.0",
        "digest": "b" * 64,
    }


@pytest.mark.issue(167)
def test_verify_rejects_success_with_blocking_findings(
    myst_profile: dict[str, object],
    stage_chain: dict[str, dict[str, object]],
) -> None:
    validation = build_validation(
        bundle_digest=str(stage_chain["apply"]["bundle_digest"]),
        validator=myst_profile["validator"],  # type: ignore[arg-type]
        passed=True,
        findings=[
            {
                "feature_id": "breaking.path.remove",
                "severity": "breaking",
                "action": "block",
                "path": "/v1/x",
            }
        ],
        diagnostics_digest="6" * 64,
    )
    stages = {**stage_chain, "validate": validation}
    sealed = seal_migration_receipt(
        myst_profile,
        mode="validate",
        source_manifest_digest=SOURCE_MANIFEST_DIGEST,
        stage_outputs=stages,
        validation=validation,
        require_success=False,
    )
    # Sealer must not leave validation_passed true with blocking findings.
    assert sealed["receipt"]["validation_passed"] is False

    forged = dict(sealed["receipt"])
    forged["validation_passed"] = True
    forged["receipt_digest"] = compute_receipt_digest(forged)
    rejected = verify_migration_receipt(
        forged,
        profile=myst_profile,
        validation=validation,
    )
    assert rejected["verified"] is False
    assert rejected["error"] == "validation_passed_with_blocking_findings"


@pytest.mark.issue(167)
def test_verify_rejects_tampered_receipt_digest(
    myst_profile: dict[str, object],
    stage_chain: dict[str, dict[str, object]],
) -> None:
    validation = build_validation(
        bundle_digest=str(stage_chain["apply"]["bundle_digest"]),
        validator=myst_profile["validator"],  # type: ignore[arg-type]
        passed=True,
        findings=[],
        diagnostics_digest="7" * 64,
    )
    sealed = seal_migration_receipt(
        myst_profile,
        mode="validate",
        source_manifest_digest=SOURCE_MANIFEST_DIGEST,
        stage_outputs={**stage_chain, "validate": validation},
        validation=validation,
        require_success=True,
    )
    tampered = dict(sealed["receipt"])
    tampered["profile_version"] = "9.9.9"
    # Leave old digest → mismatch
    result = verify_migration_receipt(tampered, profile=myst_profile)
    assert result["verified"] is False
    assert result["error"] == "receipt_digest_mismatch"
