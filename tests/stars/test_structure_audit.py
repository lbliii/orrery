"""Tests for orrery/structure-audit — pure protocol star (#223)."""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from dogfood import verify_receipt as verify_envelope_wire
from stars.builtins import builtin_registry
from stars.structure_audit.contract import tool_schemas
from stars.structure_audit.corpus import CORPUS
from stars.structure_audit.service import audit
from stars.structure_audit.skill import build_skill
from tests.stars.helpers import (
    assert_manifest_publish_corpus,
    assert_payload_keys,
    assert_tool_schema_keys,
    load_star_manifest,
)


@pytest.mark.issue(223)
def test_clean_single_file_passes() -> None:
    result = audit(
        [
            {
                "path": "docs/readme.md",
                "content": "---\ntitle: Readme\n---\n\n# Readme\n\nHello.\n",
            }
        ]
    )
    assert_payload_keys(result, ("findings", "finding_codes", "file_count", "passed"))
    assert result["passed"] is True
    assert result["findings"] == []


@pytest.mark.issue(223)
def test_heading_skip_and_missing_title() -> None:
    result = audit(
        [
            {
                "path": "docs/guide.md",
                "content": "---\nstatus: draft\n---\n\n# Guide\n\n### Too deep\n",
            }
        ]
    )
    assert result["passed"] is False
    assert set(result["finding_codes"]) >= {"heading_level_skip", "frontmatter_missing_title"}
    for item in result["findings"]:
        remediation = item.get("remediation")
        assert isinstance(remediation, str) and remediation.strip()


@pytest.mark.issue(314)
def test_failing_findings_include_remediation() -> None:
    result = audit(
        [
            {
                "path": "docs/guide.md",
                "content": "---\nstatus: draft\n---\n\n# Guide\n\n### Too deep\n",
            }
        ]
    )
    assert result["passed"] is False
    assert result["findings"]
    remediations = [
        item["remediation"]
        for item in result["findings"]
        if isinstance(item.get("remediation"), str) and item["remediation"].strip()
    ]
    assert remediations
    skip = next(
        item for item in result["findings"] if item["code"] == "heading_level_skip"
    )
    assert "at most one" in str(skip["remediation"]).lower()


@pytest.mark.issue(223)
def test_orphan_detection() -> None:
    result = audit(
        [
            {
                "path": "docs/index.md",
                "content": "# Index\n\nSee [a](docs/a.md).\n",
            },
            {
                "path": "docs/a.md",
                "content": "# A\n\nLinked.\n",
            },
            {
                "path": "docs/orphan.md",
                "content": "# Orphan\n\nAlone.\n",
            },
        ]
    )
    codes = {item["code"] for item in result["findings"]}
    assert "orphan_file" in codes
    orphan_paths = [item["path"] for item in result["findings"] if item["code"] == "orphan_file"]
    assert orphan_paths == ["docs/orphan.md"]


@pytest.mark.issue(223)
class TestL0StructureAudit:
    def test_contract_tools_and_empty_egress(self) -> None:
        manifest = load_star_manifest("structure_audit")
        assert manifest["policy"]["allowed_egress"] == []
        assert_tool_schema_keys(tool_schemas(), {"audit"})
        assert_manifest_publish_corpus("structure_audit")
        assert CORPUS

    def test_invalid_files_fails_loud(self) -> None:
        assert audit(None)["error"] == "files_invalid"  # type: ignore[arg-type]


@pytest.mark.issue(223)
def test_envelope_signs_and_verifies(monkeypatch: pytest.MonkeyPatch) -> None:
    private = Ed25519PrivateKey.generate()
    monkeypatch.setenv("ORRERY_STAR_PRIVATE_KEY", private.private_bytes_raw().hex())
    monkeypatch.setenv("ORRERY_STAR_KEY_ID", "stars-2026-08")
    skill = build_skill()
    envelope = next(item for item in skill._pending if item.name == "audit").handler(
        files=[
            {
                "path": "docs/readme.md",
                "content": "---\ntitle: Readme\n---\n\n# Readme\n\nHello.\n",
            }
        ]
    )
    assert verify_envelope_wire(envelope.to_wire(), skill=skill) is True
    assert envelope.payload["passed"] is True


@pytest.mark.issue(223)
def test_package_contract_and_registry() -> None:
    assert {item.name for item in build_skill()._pending} == {"audit"}
    definition = next(
        item for item in builtin_registry() if item.name == "orrery/structure-audit"
    )
    assert definition.direct_mcp_path == "/stars/structure-audit/mcp"
    assert definition.publish_corpus.endswith(".corpus:CORPUS")
