"""Tests for orrery/manifest-preflight — pure protocol star (#222)."""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from dogfood import verify_receipt as verify_envelope_wire
from stars.builtins import builtin_registry
from stars.manifest_bind.service import bind
from stars.manifest_preflight.contract import POLICY_DOCS_ONLY, POLICY_MAX_100, tool_schemas
from stars.manifest_preflight.corpus import CORPUS
from stars.manifest_preflight.service import check
from stars.manifest_preflight.skill import build_skill
from tests.stars.helpers import (
    assert_manifest_publish_corpus,
    assert_payload_keys,
    assert_tool_schema_keys,
    load_star_manifest,
)

DOCS_FILE = {
    "path": "docs/readme.md",
    "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "size": 12,
}
ROOT_FILE = {
    "path": "README.md",
    "sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "size": 4,
}


@pytest.mark.issue(222)
def test_docs_only_policy_pass_and_fail() -> None:
    ok = check([DOCS_FILE], POLICY_DOCS_ONLY)
    assert_payload_keys(ok, ("passed", "policy", "violations", "violation_codes"))
    assert ok["passed"] is True
    assert ok["violation_codes"] == []

    bad = check([DOCS_FILE, ROOT_FILE], POLICY_DOCS_ONLY)
    assert bad["passed"] is False
    assert bad["violation_codes"] == ["path_not_docs"]
    assert bad["violations"] == [
        {
            "code": "path_not_docs",
            "path": "README.md",
            "remediation": (
                "Move the file under docs/ with a docs-like suffix (.md, .rst, .txt, "
                ".toml, .yaml, .yml, .json), or remove it from the manifest."
            ),
        }
    ]


@pytest.mark.issue(322)
def test_failing_violations_include_remediation() -> None:
    bad = check([DOCS_FILE, ROOT_FILE], POLICY_DOCS_ONLY)
    remediations = [
        item["remediation"]
        for item in bad["violations"]
        if isinstance(item.get("remediation"), str) and item["remediation"].strip()
    ]
    assert remediations
    assert bad["passed"] is False
    assert bad["violation_codes"] == ["path_not_docs"]


@pytest.mark.issue(222)
def test_max_100_files_policy() -> None:
    files = [
        {
            "path": f"docs/f{index:03d}.md",
            "sha256": f"{index:064x}",
            "size": 1,
        }
        for index in range(101)
    ]
    result = check(files, POLICY_MAX_100)
    assert result["passed"] is False
    assert result["violation_codes"] == ["too_many_files"]

    assert check(files[:100], POLICY_MAX_100)["passed"] is True


@pytest.mark.issue(222)
def test_optional_manifest_digest_must_match() -> None:
    bound = bind([DOCS_FILE])
    digest = str(bound["manifest_digest"])
    assert check([DOCS_FILE], POLICY_DOCS_ONLY, digest)["passed"] is True
    mismatch = check([DOCS_FILE], POLICY_DOCS_ONLY, "0" * 64)
    assert mismatch["error"] == "manifest_digest_mismatch"


@pytest.mark.issue(222)
def test_unknown_policy_fails_loud() -> None:
    assert check([DOCS_FILE], "orrery/nope@v1")["error"] == "policy_unknown"


@pytest.mark.issue(222)
class TestL0ManifestPreflight:
    def test_contract_tools_and_empty_egress(self) -> None:
        manifest = load_star_manifest("manifest_preflight")
        assert manifest["policy"]["allowed_egress"] == []
        assert_tool_schema_keys(tool_schemas(), {"check"})
        assert_manifest_publish_corpus("manifest_preflight")
        assert CORPUS


@pytest.mark.issue(222)
def test_envelope_and_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    private = Ed25519PrivateKey.generate()
    monkeypatch.setenv("ORRERY_STAR_PRIVATE_KEY", private.private_bytes_raw().hex())
    monkeypatch.setenv("ORRERY_STAR_KEY_ID", "stars-2026-08")
    skill = build_skill()
    envelope = next(item for item in skill._pending if item.name == "check").handler(
        files=[DOCS_FILE],
        policy=POLICY_DOCS_ONLY,
    )
    assert verify_envelope_wire(envelope.to_wire(), skill=skill) is True
    definition = next(
        item for item in builtin_registry() if item.name == "orrery/manifest-preflight"
    )
    assert definition.direct_mcp_path == "/stars/manifest-preflight/mcp"
