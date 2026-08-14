"""Tests for orrery/kida-ready constellation (#403)."""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from catalog.agent_card import KIDA_READY_DISPOSITIONS, require_card
from catalog.constellation import policy_for
from catalog.sync import build_star_records
from dogfood import verify_receipt as verify_envelope_wire
from stars.builtins import build_direct_skills, builtin_registry
from stars.kida_check.corpus import _BADGE_TEMPLATE as _BADGE_TYPO_TEMPLATE
from stars.kida_ready.service import run
from stars.kida_ready.skill import build_skill
from stars.kida_render.corpus import _BADGE_TEMPLATE as _BADGE_FIXED_TEMPLATE

_BADGE_DATA = {"count": 5, "label": "Messages"}

_BAD_TEMPLATES = [
    {
        "path": "templates/dashboard.html",
        "content": _BADGE_TYPO_TEMPLATE,
    }
]

_GOOD_TEMPLATES = [
    {
        "path": "templates/dashboard.html",
        "content": _BADGE_FIXED_TEMPLATE,
    }
]


@pytest.mark.issue(403)
def test_needs_work_without_render_on_badge_typo() -> None:
    result = run(_BAD_TEMPLATES, _BADGE_DATA)
    assert result["constellation"] == "orrery/kida-ready"
    assert result["disposition"] == "needs-work"
    assert result["stages"]["kida-check"]["passed"] is False
    assert result["stages"]["gate"]["passed"] is False
    assert "kida-render" not in result["stages"]


@pytest.mark.issue(403)
def test_ready_includes_render_digests_on_fixed_badge() -> None:
    result = run(_GOOD_TEMPLATES, _BADGE_DATA)
    assert result["disposition"] == "ready"
    assert result["stages"]["kida-check"]["passed"] is True
    assert result["stages"]["gate"]["passed"] is True
    render_stage = result["stages"]["kida-render"]
    assert render_stage["output_digest"]
    assert render_stage["template_digest"]
    assert render_stage["data_digest"]
    assert '<span class="badge">5 Messages</span>' in str(render_stage["html"])


@pytest.mark.issue(403)
def test_inconclusive_on_invalid_templates() -> None:
    result = run(None, _BADGE_DATA)  # type: ignore[arg-type]
    assert result["disposition"] == "inconclusive"
    assert result["stages"]["kida-check"]["error"] == "templates_invalid"


@pytest.mark.issue(403)
def test_agent_card_subtree_contract_sync_only() -> None:
    card = require_card("orrery/kida-ready")
    assert card.dispositions == KIDA_READY_DISPOSITIONS
    contract = card.as_dict()["subtree_contract"]
    assert contract["pause_policy"]["allowed"] is False
    stage_ids = [stage["id"] for stage in contract["stages"]]
    assert stage_ids == [
        "kida-check",
        "gate",
        "kida-render",
        "artifact-seal",
    ]
    seal = contract["stages"][-1]
    assert seal["role"] == "composite"
    assert "star_ref" not in seal
    assert contract["composite_receipt_fields"]["disposition"] == list(
        KIDA_READY_DISPOSITIONS
    )


@pytest.mark.issue(403)
def test_registry_policy_and_signed_skill() -> None:
    registry = builtin_registry()
    definition = registry.get("orrery/kida-ready")
    assert definition.kind == "constellation"
    assert definition.direct_mcp_path == "/constellations/kida-ready/mcp"
    assert definition.tools == ("run",)
    graph = policy_for("orrery/kida-ready")
    assert graph is not None
    assert [node.star_ref for node in graph.nodes if node.star_ref] == [
        "orrery/kida-check",
        "orrery/kida-render",
    ]
    record = next(
        record
        for record in build_star_records(registry, build_direct_skills(registry))
        if record.name == "orrery/kida-ready"
    )
    assert record.kind == "constellation" and record.tools == ("run",)


@pytest.mark.issue(403)
def test_envelope_signs_and_verifies(monkeypatch: pytest.MonkeyPatch) -> None:
    private = Ed25519PrivateKey.generate()
    monkeypatch.setenv("ORRERY_STAR_PRIVATE_KEY", private.private_bytes_raw().hex())
    monkeypatch.setenv("ORRERY_STAR_KEY_ID", "stars-2026-08")
    skill = build_skill()
    envelope = next(item for item in skill._pending if item.name == "run").handler(
        templates=_GOOD_TEMPLATES,
        data=_BADGE_DATA,
        validate_calls=True,
        strict=False,
        surface="html",
    )
    assert envelope.signature
    assert envelope.payload["constellation"] == "orrery/kida-ready"
    assert envelope.payload["disposition"] == "ready"
    verify_envelope_wire(envelope.to_wire())
