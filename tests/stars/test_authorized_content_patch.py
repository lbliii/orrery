"""Tests for orrery/authorized-content-patch constellation (#215)."""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from catalog.agent_card import (
    AUTHORIZED_CONTENT_PATCH_DISPOSITIONS,
    require_card,
)
from catalog.constellation import policy_for
from catalog.sync import build_star_records
from dogfood import verify_receipt as verify_envelope_wire
from stars.authorized_content_patch.service import run
from stars.authorized_content_patch.skill import build_skill
from stars.builtins import build_direct_skills, builtin_registry
from stars.write_authority_check.contract import POLICY_EXPLICIT_PATHS
from stars.write_authority_check.service import grant_digest

BEFORE = [
    {
        "path": "docs/readme.md",
        "content": "---\ntitle: Readme\n---\n\n# Readme\n\nHello.\n",
    }
]

AFTER = [
    {
        "path": "docs/readme.md",
        "content": (
            "---\ntitle: Readme\n---\n\n# Readme\n\n"
            "See [Python](https://docs.python.org/3/).\n"
        ),
    }
]

PATHS = ["docs/readme.md"]
DIGEST = grant_digest(POLICY_EXPLICIT_PATHS, PATHS)


def _authority(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "policy": POLICY_EXPLICIT_PATHS,
        "allowed_paths": list(PATHS),
        "grant_digest": DIGEST,
    }
    base.update(overrides)
    return base


def _ok_transport(url: str, *, timeout: float) -> tuple[str, int]:
    return url, 200


@pytest.mark.issue(215)
def test_authorized_disposition_over_clean_edit() -> None:
    result = run(BEFORE, AFTER, _authority(), link_transport=_ok_transport)
    assert result["constellation"] == "orrery/authorized-content-patch"
    assert result["disposition"] == "authorized"
    assert result["chain"] == "signed-envelope-chain"
    assert result["policy_digest"].startswith("sha256:")
    assert {"digest", "key_id"} <= set(result["release"])
    stages = result["stages"]
    assert stages["manifest-preflight"]["passed"] is True
    assert stages["write-authority-check"]["authorized"] is True
    assert stages["patch-capture"]["patch_digest"]
    assert stages["patch-capture"]["changed_paths"] == ["docs/readme.md"]
    component_names = {c["name"] for c in result["components"]}
    assert "orrery/write-authority-check" in component_names
    assert "orrery/patch-capture" in component_names
    assert any("Does not apply patches" in item for item in result["limitations"])


@pytest.mark.issue(215)
def test_denied_when_grant_digest_mismatches() -> None:
    result = run(
        BEFORE,
        AFTER,
        _authority(grant_digest="b" * 64),
        link_transport=_ok_transport,
    )
    assert result["disposition"] == "denied"
    assert "grant_digest_mismatch" in result["stages"]["write-authority-check"]["codes"]


@pytest.mark.issue(215)
def test_denied_when_changed_path_outside_grant() -> None:
    after = [
        {
            "path": "docs/other.md",
            "content": "---\ntitle: Other\n---\n\n# Other\n\nHello.\n",
        }
    ]
    result = run(BEFORE, after, _authority(), link_transport=_ok_transport)
    assert result["disposition"] == "denied"
    assert result["stages"]["path-grant"]["codes"] == ["path_not_granted"]


@pytest.mark.issue(215)
def test_needs_work_when_structure_findings() -> None:
    after = [
        {
            "path": "docs/guide.md",
            "content": "---\nstatus: draft\n---\n\n# Guide\n\n### Too deep\n",
        }
    ]
    authority = {
        "policy": POLICY_EXPLICIT_PATHS,
        "allowed_paths": ["docs/guide.md"],
        "grant_digest": grant_digest(POLICY_EXPLICIT_PATHS, ["docs/guide.md"]),
    }
    result = run(BEFORE, after, authority, link_transport=_ok_transport)
    assert result["disposition"] == "needs-work"
    assert result["stages"]["structure-audit"]["passed"] is False
    assert "write-authority-check" not in result["stages"]
    assert "patch-capture" not in result["stages"]


@pytest.mark.issue(215)
def test_inconclusive_on_invalid_after_bundle() -> None:
    result = run(BEFORE, None, _authority())  # type: ignore[arg-type]
    assert result["disposition"] == "inconclusive"
    assert result["stages"]["bundle"]["error"] == "files_invalid"


@pytest.mark.issue(215)
def test_agent_card_subtree_contract_and_not_for() -> None:
    card = require_card("orrery/authorized-content-patch")
    assert card.write_authority == "read-only"
    assert card.dispositions == AUTHORIZED_CONTENT_PATCH_DISPOSITIONS
    payload = card.as_dict()
    assert "subtree_contract" in payload
    assert any(
        "filesystem" in item.lower() or "apply" in item.lower() for item in card.not_for
    )
    contract = payload["subtree_contract"]
    assert contract["pause_policy"]["allowed"] is False
    assert contract["lease_rule"] == "waiting_never_holds_worker_lease"
    stage_ids = [stage["id"] for stage in contract["stages"]]
    assert stage_ids == [
        "manifest-bind",
        "manifest-preflight",
        "structure-audit",
        "link-check-bounded",
        "write-authority-check",
        "patch-capture",
        "artifact-seal",
    ]
    refs = [stage.get("star_ref") for stage in contract["stages"] if stage.get("star_ref")]
    assert "orrery/write-authority-check" in refs
    assert "orrery/patch-capture" in refs
    seal = contract["stages"][-1]
    assert seal["role"] == "composite"
    assert "star_ref" not in seal
    assert contract["composite_receipt_fields"]["disposition"] == list(
        AUTHORIZED_CONTENT_PATCH_DISPOSITIONS
    )


@pytest.mark.issue(215)
def test_registry_policy_and_signed_skill() -> None:
    registry = builtin_registry()
    definition = registry.get("orrery/authorized-content-patch")
    assert definition.kind == "constellation"
    assert definition.direct_mcp_path == "/constellations/authorized-content-patch/mcp"
    assert definition.tools == ("run",)
    graph = policy_for("orrery/authorized-content-patch")
    assert graph is not None
    assert [node.star_ref for node in graph.nodes if node.star_ref] == [
        "orrery/manifest-bind",
        "orrery/manifest-preflight",
        "orrery/structure-audit",
        "orrery/link-check-bounded",
        "orrery/write-authority-check",
        "orrery/patch-capture",
    ]
    record = next(
        record
        for record in build_star_records(registry, build_direct_skills(registry))
        if record.name == "orrery/authorized-content-patch"
    )
    assert record.kind == "constellation" and record.tools == ("run",)


@pytest.mark.issue(215)
def test_envelope_signs_and_verifies(monkeypatch: pytest.MonkeyPatch) -> None:
    private = Ed25519PrivateKey.generate()
    monkeypatch.setenv("ORRERY_STAR_PRIVATE_KEY", private.private_bytes_raw().hex())
    monkeypatch.setenv("ORRERY_STAR_KEY_ID", "stars-2026-08")
    skill = build_skill()
    no_egress_before = [
        {
            "path": "docs/readme.md",
            "content": "---\ntitle: Readme\n---\n\n# Readme\n\nHello.\n",
        }
    ]
    no_egress_after = [
        {
            "path": "docs/readme.md",
            "content": "---\ntitle: Readme\n---\n\n# Readme\n\nHello world.\n",
        }
    ]
    envelope = next(item for item in skill._pending if item.name == "run").handler(
        before=no_egress_before,
        after=no_egress_after,
        authority=_authority(),
        policy="orrery/docs-only@v1",
        max_link_count=20,
    )
    assert envelope.signature
    assert envelope.payload["constellation"] == "orrery/authorized-content-patch"
    assert envelope.payload["disposition"] == "authorized"
    verify_envelope_wire(envelope.to_wire())
