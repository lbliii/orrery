"""Tests for orrery/kida-check — static Kida validation star (#401)."""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from dogfood import verify_receipt as verify_envelope_wire
from stars._core.attribution import PAYLOAD_VIA
from stars.builtins import builtin_registry
from stars.kida_check.contract import tool_schemas
from stars.kida_check.corpus import _BADGE_TEMPLATE, CORPUS
from stars.kida_check.service import check
from stars.kida_check.skill import build_skill
from tests.stars.helpers import (
    assert_manifest_publish_corpus,
    assert_payload_keys,
    assert_tool_schema_keys,
    load_star_manifest,
)


@pytest.mark.issue(401)
def test_clean_template_passes() -> None:
    result = check(
        [
            {
                "path": "templates/page.html",
                "content": "{% def card(title: str) %}{{ title }}{% enddef %}\n",
            }
        ]
    )
    assert_payload_keys(
        result,
        (
            "findings",
            "finding_codes",
            "template_count",
            "passed",
            "validate_calls",
            "strict",
        ),
    )
    assert result["passed"] is True
    assert result["findings"] == []


@pytest.mark.issue(401)
def test_badge_typo_story_finds_cmp_codes() -> None:
    result = check(
        [
            {
                "path": "templates/dashboard.html",
                "content": _BADGE_TEMPLATE,
            }
        ]
    )
    assert result["passed"] is False
    assert set(result["finding_codes"]) >= {"K-CMP-001", "K-CMP-002"}
    for item in result["findings"]:
        assert isinstance(item.get("message"), str) and item["message"].strip()


@pytest.mark.issue(401)
def test_validate_calls_can_be_disabled() -> None:
    result = check(
        [
            {
                "path": "templates/dashboard.html",
                "content": _BADGE_TEMPLATE,
            }
        ],
        validate_calls=False,
    )
    assert result["validate_calls"] is False
    assert "K-CMP-001" not in result["finding_codes"]
    assert "K-CMP-002" not in result["finding_codes"]


@pytest.mark.issue(401)
class TestL0KidaCheck:
    def test_contract_tools_and_empty_egress(self) -> None:
        manifest = load_star_manifest("kida_check")
        assert manifest["policy"]["allowed_egress"] == []
        assert_tool_schema_keys(tool_schemas(), {"check"})
        assert_manifest_publish_corpus("kida_check")
        assert CORPUS

    def test_invalid_templates_fails_loud(self) -> None:
        assert check(None)["error"] == "templates_invalid"  # type: ignore[arg-type]


@pytest.mark.issue(401)
def test_envelope_signs_and_verifies(monkeypatch: pytest.MonkeyPatch) -> None:
    private = Ed25519PrivateKey.generate()
    monkeypatch.setenv("ORRERY_STAR_PRIVATE_KEY", private.private_bytes_raw().hex())
    monkeypatch.setenv("ORRERY_STAR_KEY_ID", "stars-2026-08")
    skill = build_skill()
    envelope = next(item for item in skill._pending if item.name == "check").handler(
        templates=[
            {
                "path": "templates/page.html",
                "content": "{% def card(title: str) %}{{ title }}{% enddef %}\n",
            }
        ]
    )
    assert verify_envelope_wire(envelope.to_wire(), skill=skill) is True
    assert envelope.payload["passed"] is True
    assert envelope.payload["via"] == PAYLOAD_VIA


@pytest.mark.issue(401)
def test_success_seal_includes_payload_via(monkeypatch: pytest.MonkeyPatch) -> None:
    private = Ed25519PrivateKey.generate()
    monkeypatch.setenv("ORRERY_STAR_PRIVATE_KEY", private.private_bytes_raw().hex())
    monkeypatch.setenv("ORRERY_STAR_KEY_ID", "stars-2026-08")
    skill = build_skill()
    envelope = next(item for item in skill._pending if item.name == "check").handler(
        templates=[
            {
                "path": "templates/page.html",
                "content": "{% def card(title: str) %}{{ title }}{% enddef %}\n",
            }
        ]
    )
    payload = envelope.to_wire()["payload"]
    assert payload["via"]["line"] == PAYLOAD_VIA["line"]
    assert payload["via"]["sky"] == PAYLOAD_VIA["sky"]


@pytest.mark.issue(401)
def test_package_contract_and_registry() -> None:
    assert {item.name for item in build_skill()._pending} == {"check"}
    definition = next(
        item for item in builtin_registry() if item.name == "orrery/kida-check"
    )
    assert definition.direct_mcp_path == "/stars/kida-check/mcp"
    assert definition.publish_corpus.endswith(".corpus:CORPUS")
