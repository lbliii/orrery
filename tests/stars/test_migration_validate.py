"""Tests for migration validator adapter (ADR 0008) — issue #167."""

from __future__ import annotations

import pytest

from stars._core.migration_run import MigrationRunStore, build_change_bundle
from stars._core.migration_validate import (
    bound_findings,
    redact_diagnostics,
    run_validate_stage,
    validate_change_bundle,
)
from tests.stars.test_migration_profile import MYST_PROFILE_BASE, _with_digest

SOURCE_MANIFEST_DIGEST = "e" * 64
PLAN_DIGEST = "1" * 64


@pytest.fixture
def myst_profile() -> dict[str, object]:
    return _with_digest(MYST_PROFILE_BASE)


@pytest.fixture
def sample_bundle() -> dict[str, object]:
    return build_change_bundle(
        plan_digest=PLAN_DIGEST,
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


@pytest.mark.issue(167)
def test_validator_failure_sets_validation_passed_false(
    myst_profile: dict[str, object],
    sample_bundle: dict[str, object],
) -> None:
    result = validate_change_bundle(
        myst_profile,
        sample_bundle,
        findings=[
            {
                "feature_id": "nav.link.break",
                "severity": "breaking",
                "action": "block",
                "path": "docs/page.md",
                "message": "broken link",
            }
        ],
        checker_passed=True,
    )
    assert "error" not in result
    assert result["validation_passed"] is False
    assert result["validation"]["passed"] is False


@pytest.mark.issue(167)
def test_checker_failure_cannot_report_success(
    myst_profile: dict[str, object],
    sample_bundle: dict[str, object],
) -> None:
    def failing_checker(profile: dict[str, object], bundle: dict[str, object]) -> dict[str, object]:
        assert profile["profile_id"] == myst_profile["profile_id"]
        assert bundle["bundle_digest"] == sample_bundle["bundle_digest"]
        return {
            "passed": False,
            "findings": [{"feature_id": "mdx.parse", "class": "malformed", "path": "x.mdx"}],
            "diagnostics": {
                "source_bytes": b"SECRET_SOURCE",
                "message": "parse failed",
                "detail": "ok-to-keep",
            },
        }

    result = validate_change_bundle(
        myst_profile,
        sample_bundle,
        checker=failing_checker,
    )
    assert result["validation_passed"] is False
    assert result["validation"]["passed"] is False
    diagnostics = result["diagnostics"]
    assert "source_bytes" not in diagnostics.get("summary", {})
    assert "SECRET_SOURCE" not in str(diagnostics)
    assert "source_bytes" in diagnostics["redacted_keys"]


@pytest.mark.issue(167)
def test_diagnostics_bounded_and_redacted(
    myst_profile: dict[str, object],
) -> None:
    retention = myst_profile["retention_redaction"]
    huge = "x" * 2000
    safe, digest = redact_diagnostics(
        {
            "message": huge,
            "source_bytes": "RAW",
            "full_patch_text": "diff --git",
            "note": "safe",
        },
        retention,
    )
    assert isinstance(digest, str) and len(digest) == 64
    assert len(safe["summary"]["message"].encode()) <= 512
    assert "source_bytes" not in safe["summary"]
    assert "full_patch_text" not in safe["summary"]
    assert "RAW" not in str(safe)
    assert "source_bytes" in safe["redacted_keys"]

    findings = bound_findings(
        [
            {
                "feature_id": "a",
                "message": "m" * 2000,
                "source_bytes": "nope",
                "path": "p.md",
            }
        ],
        retention,
    )
    assert "source_bytes" not in findings[0]
    assert len(findings[0]["message"].encode("utf-8")) <= 512


@pytest.mark.issue(167)
def test_successful_validation_under_pinned_target(
    myst_profile: dict[str, object],
    sample_bundle: dict[str, object],
) -> None:
    result = validate_change_bundle(
        myst_profile,
        sample_bundle,
        findings=[{"feature_id": "md.heading", "class": "safe", "path": "docs/page.md"}],
        checker_passed=True,
        diagnostics={"message": "ok", "counts": {"files": 1}},
    )
    assert result["validation_passed"] is True
    assert result["validation"]["passed"] is True
    assert result["validation"]["bundle_digest"] == sample_bundle["bundle_digest"]
    assert result["target"] == {"kind": "mdx", "version": "3.0.0"}
    assert result["validator"]["name"] == "orrery/docs-mdx-validate"
    assert result["validator"]["version"] == "1.0.0"
    assert result["validator"]["digest"] == "b" * 64


@pytest.mark.issue(167)
def test_run_validate_stage_persists_failure(
    myst_profile: dict[str, object],
    sample_bundle: dict[str, object],
) -> None:
    store = MigrationRunStore()
    sealed = run_validate_stage(
        store,
        profile=myst_profile,
        source_manifest_digest=SOURCE_MANIFEST_DIGEST,
        bundle=sample_bundle,
        checker_passed=False,
        findings=[{"feature_id": "x", "class": "malformed", "path": "a.md"}],
        diagnostics="failure without source",
    )
    assert sealed["validation_passed"] is False
    assert sealed["output"]["passed"] is False
    assert sealed["reused"] is False
