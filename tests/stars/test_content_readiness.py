"""Tests for orrery/content-readiness constellation (#213)."""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from catalog.agent_card import CONTENT_READINESS_DISPOSITIONS, require_card
from catalog.constellation import policy_for
from catalog.sync import build_star_records
from dogfood import verify_receipt as verify_envelope_wire
from stars.builtins import build_direct_skills, builtin_registry
from stars.content_readiness.service import run
from stars.content_readiness.skill import build_skill

CLEAN_BUNDLE = [
    {
        "path": "docs/readme.md",
        "content": (
            "---\ntitle: Readme\n---\n\n# Readme\n\n"
            "See [Python](https://docs.python.org/3/).\n"
        ),
    }
]

NEEDS_WORK_BUNDLE = [
    {
        "path": "docs/guide.md",
        "content": "---\nstatus: draft\n---\n\n# Guide\n\n### Too deep\n",
    }
]


def _ok_transport(url: str, *, timeout: float) -> tuple[str, int]:
    return url, 200


@pytest.mark.issue(213)
def test_ready_disposition_over_clean_docs_bundle() -> None:
    result = run(CLEAN_BUNDLE, link_transport=_ok_transport)
    assert result["constellation"] == "orrery/content-readiness"
    assert result["disposition"] == "ready"
    assert result["chain"] == "signed-envelope-chain"
    assert result["policy_digest"].startswith("sha256:")
    assert {"digest", "key_id"} <= set(result["release"])
    stages = result["stages"]
    assert stages["manifest-preflight"]["passed"] is True
    assert stages["structure-audit"]["passed"] is True
    assert stages["link-check-bounded"]["passed"] is True
    component_names = {c["name"] for c in result["components"]}
    assert "orrery/write-authority-check" not in component_names
    assert "orrery/patch-capture" not in component_names
    assert result["stages"]["manifest-bind"]["manifest_digest"]

@pytest.mark.issue(213)
def test_needs_work_when_structure_findings() -> None:
    result = run(NEEDS_WORK_BUNDLE, link_transport=_ok_transport)
    assert result["disposition"] == "needs-work"
    assert result["stages"]["structure-audit"]["passed"] is False


@pytest.mark.issue(213)
def test_inconclusive_on_invalid_bundle() -> None:
    result = run(None)  # type: ignore[arg-type]
    assert result["disposition"] == "inconclusive"
    assert result["stages"]["bundle"]["error"] == "files_invalid"


@pytest.mark.issue(213)
def test_inconclusive_when_link_cap_exceeded() -> None:
    bundle = [
        {
            "path": "docs/links.md",
            "content": (
                "---\ntitle: Links\n---\n\n# Links\n\n"
                + "\n".join(f"[n{i}](https://example.com/{i})" for i in range(5))
                + "\n"
            ),
        }
    ]
    result = run(bundle, max_link_count=2, link_transport=_ok_transport)
    assert result["disposition"] == "inconclusive"
    assert result["stages"]["link-check-bounded"]["error"] == "link_count_exceeded"


@pytest.mark.issue(213)
def test_agent_card_subtree_contract_sync_only() -> None:
    card = require_card("orrery/content-readiness")
    assert card.write_authority == "read-only"
    assert card.dispositions == CONTENT_READINESS_DISPOSITIONS
    contract = card.as_dict()["subtree_contract"]
    assert contract["pause_policy"]["allowed"] is False
    assert contract["lease_rule"] == "waiting_never_holds_worker_lease"
    stage_ids = [stage["id"] for stage in contract["stages"]]
    assert stage_ids == [
        "manifest-bind",
        "manifest-preflight",
        "structure-audit",
        "link-check-bounded",
        "artifact-seal",
    ]
    seal = contract["stages"][-1]
    assert seal["role"] == "composite"
    assert "star_ref" not in seal
    assert contract["composite_receipt_fields"]["disposition"] == list(
        CONTENT_READINESS_DISPOSITIONS
    )
    refs = [stage.get("star_ref") for stage in contract["stages"] if stage.get("star_ref")]
    assert "orrery/write-authority-check" not in refs
    assert "orrery/patch-capture" not in refs


@pytest.mark.issue(213)
def test_registry_policy_and_signed_skill() -> None:
    registry = builtin_registry()
    definition = registry.get("orrery/content-readiness")
    assert definition.kind == "constellation"
    assert definition.direct_mcp_path == "/constellations/content-readiness/mcp"
    assert definition.tools == ("run",)
    graph = policy_for("orrery/content-readiness")
    assert graph is not None
    assert [node.star_ref for node in graph.nodes if node.star_ref] == [
        "orrery/manifest-bind",
        "orrery/manifest-preflight",
        "orrery/structure-audit",
        "orrery/link-check-bounded",
    ]
    record = next(
        record
        for record in build_star_records(registry, build_direct_skills(registry))
        if record.name == "orrery/content-readiness"
    )
    assert record.kind == "constellation" and record.tools == ("run",)


@pytest.mark.issue(213)
def test_envelope_signs_and_verifies(monkeypatch: pytest.MonkeyPatch) -> None:
    private = Ed25519PrivateKey.generate()
    monkeypatch.setenv("ORRERY_STAR_PRIVATE_KEY", private.private_bytes_raw().hex())
    monkeypatch.setenv("ORRERY_STAR_KEY_ID", "stars-2026-08")
    skill = build_skill()
    no_egress_bundle = [
        {
            "path": "docs/readme.md",
            "content": "---\ntitle: Readme\n---\n\n# Readme\n\nHello.\n",
        }
    ]
    envelope = next(item for item in skill._pending if item.name == "run").handler(
        files=no_egress_bundle,
        policy="orrery/docs-only@v1",
        max_link_count=20,
    )
    assert envelope.signature
    assert envelope.payload["constellation"] == "orrery/content-readiness"
    assert envelope.payload["disposition"] == "ready"
    verify_envelope_wire(envelope.to_wire())
