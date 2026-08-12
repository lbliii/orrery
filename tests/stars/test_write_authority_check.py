"""Tests for orrery/write-authority-check — pure protocol star (#223)."""

from __future__ import annotations

import pytest
from chirp.skill import Skill
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from dogfood import verify_receipt as verify_envelope_wire
from stars.builtins import builtin_registry
from stars.write_authority_check.contract import POLICY_EXPLICIT_PATHS, tool_schemas
from stars.write_authority_check.corpus import CORPUS
from stars.write_authority_check.service import check, grant_digest
from stars.write_authority_check.skill import build_skill
from tests.stars.helpers import (
    assert_manifest_publish_corpus,
    assert_payload_keys,
    assert_tool_schema_keys,
    load_star_manifest,
)

MANIFEST = "a" * 64
PATHS = ["docs/plan.md", "docs/readme.md"]
DIGEST = grant_digest(POLICY_EXPLICIT_PATHS, PATHS)


def _authority(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "policy": POLICY_EXPLICIT_PATHS,
        "allowed_paths": list(PATHS),
        "grant_digest": DIGEST,
    }
    base.update(overrides)
    return base


@pytest.mark.issue(223)
def test_authorized_without_witness() -> None:
    result = check(MANIFEST, _authority())
    assert_payload_keys(result, ("authorized", "codes", "grant_digest", "manifest_digest"))
    assert result["authorized"] is True
    assert result["codes"] == []
    assert result["grant_digest"] == DIGEST
    assert result["witness_verified"] is False


@pytest.mark.issue(223)
def test_grant_digest_mismatch_denies() -> None:
    result = check(MANIFEST, _authority(grant_digest="b" * 64))
    assert result["authorized"] is False
    assert "grant_digest_mismatch" in result["codes"]
    findings = result.get("findings")
    assert isinstance(findings, list) and findings
    remediation = findings[0].get("remediation")
    assert isinstance(remediation, str) and remediation.strip()
    assert "grant_digest" in remediation.lower()


@pytest.mark.issue(322)
def test_denial_findings_include_remediation() -> None:
    result = check(MANIFEST, _authority(grant_digest="b" * 64))
    assert result["authorized"] is False
    remediations = [
        item["remediation"]
        for item in result.get("findings", [])
        if isinstance(item.get("remediation"), str) and item["remediation"].strip()
    ]
    assert remediations
    assert "grant_digest_mismatch" in result["codes"]


@pytest.mark.issue(223)
def test_witness_envelope_verifies_and_covers_paths() -> None:
    private = Ed25519PrivateKey.generate()
    public_hex = private.public_key().public_bytes_raw().hex()
    skill = Skill(
        "boundary-witness",
        version="0.1.0",
        private_key=private,
        key_id="witness-1",
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool("grant", description="witness grant")
    def grant() -> dict[str, object]:
        return {"grant_digest": DIGEST, "allowed_paths": list(PATHS)}

    envelope = next(item for item in skill._pending if item.name == "grant").handler()
    result = check(
        MANIFEST,
        _authority(witness=envelope.to_wire(), witness_public_key=public_hex),
    )
    assert result["authorized"] is True
    assert result["witness_verified"] is True


@pytest.mark.issue(223)
def test_witness_path_mismatch_denies() -> None:
    private = Ed25519PrivateKey.generate()
    public_hex = private.public_key().public_bytes_raw().hex()
    skill = Skill(
        "boundary-witness",
        version="0.1.0",
        private_key=private,
        key_id="witness-1",
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool("grant", description="witness grant")
    def grant() -> dict[str, object]:
        return {"grant_digest": DIGEST, "allowed_paths": ["docs/other.md"]}

    envelope = next(item for item in skill._pending if item.name == "grant").handler()
    result = check(
        MANIFEST,
        _authority(witness=envelope.to_wire(), witness_public_key=public_hex),
    )
    assert result["authorized"] is False
    assert "witness_paths_mismatch" in result["codes"]


@pytest.mark.issue(223)
class TestL0WriteAuthorityCheck:
    def test_contract_tools_and_empty_egress(self) -> None:
        manifest = load_star_manifest("write_authority_check")
        assert manifest["policy"]["allowed_egress"] == []
        assert_tool_schema_keys(tool_schemas(), {"check"})
        assert_manifest_publish_corpus("write_authority_check")
        assert CORPUS

    def test_invalid_manifest_fails_loud(self) -> None:
        result = check("not-hex", _authority())
        assert result["error"] == "manifest_digest_invalid"
        remediation = result.get("remediation")
        assert isinstance(remediation, str) and remediation.strip()


@pytest.mark.issue(223)
def test_envelope_signs_and_verifies(monkeypatch: pytest.MonkeyPatch) -> None:
    private = Ed25519PrivateKey.generate()
    monkeypatch.setenv("ORRERY_STAR_PRIVATE_KEY", private.private_bytes_raw().hex())
    monkeypatch.setenv("ORRERY_STAR_KEY_ID", "stars-2026-08")
    skill = build_skill()
    envelope = next(item for item in skill._pending if item.name == "check").handler(
        manifest_digest=MANIFEST,
        authority=_authority(),
    )
    assert verify_envelope_wire(envelope.to_wire(), skill=skill) is True
    assert envelope.payload["authorized"] is True


@pytest.mark.issue(223)
def test_package_contract_and_registry() -> None:
    assert {item.name for item in build_skill()._pending} == {"check"}
    definition = next(
        item for item in builtin_registry() if item.name == "orrery/write-authority-check"
    )
    assert definition.direct_mcp_path == "/stars/write-authority-check/mcp"
    assert definition.publish_corpus.endswith(".corpus:CORPUS")
