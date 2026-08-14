"""Tests for orrery/kida-render — sync Kida HTML render star (#402)."""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from dogfood import verify_receipt as verify_envelope_wire
from stars._core.attribution import PAYLOAD_VIA
from stars.builtins import builtin_registry
from stars.kida_render.contract import tool_schemas
from stars.kida_render.corpus import _BADGE_TEMPLATE, CORPUS
from stars.kida_render.service import (
    data_digest,
    output_digest,
    render,
    template_digest,
)
from stars.kida_render.skill import build_skill
from tests.stars.helpers import (
    assert_manifest_publish_corpus,
    assert_payload_keys,
    assert_tool_schema_keys,
    load_star_manifest,
)

_BADGE_DATA = {"count": 5, "label": "Messages"}


@pytest.mark.issue(402)
def test_badge_renders_expected_html() -> None:
    result = render(_BADGE_TEMPLATE, _BADGE_DATA)
    assert_payload_keys(
        result,
        (
            "html",
            "surface",
            "template_digest",
            "data_digest",
            "output_digest",
        ),
    )
    assert '<span class="badge">5 Messages</span>' in str(result["html"])
    assert result["surface"] == "html"


@pytest.mark.issue(402)
def test_digests_are_stable() -> None:
    first = render(_BADGE_TEMPLATE, _BADGE_DATA)
    second = render(_BADGE_TEMPLATE, _BADGE_DATA)
    assert first["template_digest"] == second["template_digest"]
    assert first["data_digest"] == second["data_digest"]
    assert first["output_digest"] == second["output_digest"]
    assert first["template_digest"] == template_digest(_BADGE_TEMPLATE)
    assert first["data_digest"] == data_digest(_BADGE_DATA)
    assert first["output_digest"] == output_digest(str(first["html"]))


@pytest.mark.issue(402)
def test_single_entry_bundle_renders() -> None:
    result = render(
        {
            "path": "templates/dashboard.html",
            "content": _BADGE_TEMPLATE,
        },
        _BADGE_DATA,
    )
    assert "error" not in result
    assert '<span class="badge">5 Messages</span>' in str(result["html"])


@pytest.mark.issue(402)
def test_output_too_large_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "stars.kida_render.service.MAX_OUTPUT_BYTES",
        10,
    )
    result = render(_BADGE_TEMPLATE, _BADGE_DATA)
    assert result["error"] == "output_too_large"
    assert "remediation" in result
    assert "html" not in result


@pytest.mark.issue(402)
def test_surface_invalid() -> None:
    result = render(_BADGE_TEMPLATE, _BADGE_DATA, surface="pdf")
    assert result["error"] == "surface_invalid"


@pytest.mark.issue(402)
class TestL0KidaRender:
    def test_contract_tools_and_empty_egress(self) -> None:
        manifest = load_star_manifest("kida_render")
        assert manifest["policy"]["allowed_egress"] == []
        assert_tool_schema_keys(tool_schemas(), {"render"})
        assert_manifest_publish_corpus("kida_render")
        assert CORPUS

    def test_invalid_template_fails_loud(self) -> None:
        assert render(None, _BADGE_DATA)["error"] == "template_invalid"  # type: ignore[arg-type]

    def test_invalid_data_fails_loud(self) -> None:
        assert render(_BADGE_TEMPLATE, "not-an-object")["error"] == "data_invalid"  # type: ignore[arg-type]


@pytest.mark.issue(402)
def test_envelope_signs_and_verifies(monkeypatch: pytest.MonkeyPatch) -> None:
    private = Ed25519PrivateKey.generate()
    monkeypatch.setenv("ORRERY_STAR_PRIVATE_KEY", private.private_bytes_raw().hex())
    monkeypatch.setenv("ORRERY_STAR_KEY_ID", "stars-2026-08")
    skill = build_skill()
    envelope = next(item for item in skill._pending if item.name == "render").handler(
        template=_BADGE_TEMPLATE,
        data=_BADGE_DATA,
    )
    assert verify_envelope_wire(envelope.to_wire(), skill=skill) is True
    assert '<span class="badge">5 Messages</span>' in str(envelope.payload["html"])
    assert envelope.payload["via"] == PAYLOAD_VIA


@pytest.mark.issue(402)
def test_success_seal_includes_payload_via(monkeypatch: pytest.MonkeyPatch) -> None:
    private = Ed25519PrivateKey.generate()
    monkeypatch.setenv("ORRERY_STAR_PRIVATE_KEY", private.private_bytes_raw().hex())
    monkeypatch.setenv("ORRERY_STAR_KEY_ID", "stars-2026-08")
    skill = build_skill()
    envelope = next(item for item in skill._pending if item.name == "render").handler(
        template=_BADGE_TEMPLATE,
        data=_BADGE_DATA,
    )
    payload = envelope.to_wire()["payload"]
    assert payload["via"]["line"] == PAYLOAD_VIA["line"]
    assert payload["via"]["sky"] == PAYLOAD_VIA["sky"]


@pytest.mark.issue(402)
def test_package_contract_and_registry() -> None:
    assert {item.name for item in build_skill()._pending} == {"render"}
    definition = next(
        item for item in builtin_registry() if item.name == "orrery/kida-render"
    )
    assert definition.direct_mcp_path == "/stars/kida-render/mcp"
    assert definition.publish_corpus.endswith(".corpus:CORPUS")
