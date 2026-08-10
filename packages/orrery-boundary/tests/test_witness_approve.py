"""Acceptance tests for local/witness-approve (#224)."""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from orrery_boundary.grant import POLICY_EXPLICIT_PATHS, grant_digest
from orrery_boundary.witness import witness_approve

from stars.write_authority_check.service import check
from stars.write_authority_check.service import grant_digest as hosted_grant_digest

PATHS = ["docs/plan.md", "docs/readme.md"]
MANIFEST = "a" * 64


@pytest.mark.issue(224)
def test_grant_digest_matches_hosted() -> None:
    local = grant_digest(POLICY_EXPLICIT_PATHS, PATHS)
    hosted = hosted_grant_digest(POLICY_EXPLICIT_PATHS, PATHS)
    assert local == hosted


@pytest.mark.issue(224)
def test_witness_approve_verifies_in_write_authority_check() -> None:
    private = Ed25519PrivateKey.generate()
    approved = witness_approve(PATHS, private_key=private, key_id="witness-1")
    assert "error" not in approved
    assert approved["grant_digest"] == hosted_grant_digest(POLICY_EXPLICIT_PATHS, PATHS)

    result = check(
        MANIFEST,
        {
            "policy": POLICY_EXPLICIT_PATHS,
            "allowed_paths": list(PATHS),
            "grant_digest": approved["grant_digest"],
            "witness": approved["witness"],
            "witness_public_key": approved["witness_public_key"],
        },
    )
    assert result["authorized"] is True
    assert result["codes"] == []
    assert result["witness_verified"] is True


@pytest.mark.issue(224)
def test_witness_path_mismatch_denies() -> None:
    private = Ed25519PrivateKey.generate()
    approved = witness_approve(
        ["docs/other.md"],
        private_key=private,
        key_id="witness-1",
    )
    result = check(
        MANIFEST,
        {
            "policy": POLICY_EXPLICIT_PATHS,
            "allowed_paths": list(PATHS),
            "grant_digest": hosted_grant_digest(POLICY_EXPLICIT_PATHS, PATHS),
            "witness": approved["witness"],
            "witness_public_key": approved["witness_public_key"],
        },
    )
    assert result["authorized"] is False
    assert "witness_paths_mismatch" in result["codes"]
    assert result["witness_verified"] is False
