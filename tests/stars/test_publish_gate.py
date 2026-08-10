"""Tests for orrery/publish-gate constellation (#216)."""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from catalog.agent_card import PUBLISH_GATE_DISPOSITIONS, require_card
from catalog.constellation import policy_for
from catalog.sync import build_star_records
from dogfood import verify_receipt as verify_envelope_wire
from stars.builtins import build_direct_skills, builtin_registry
from stars.publish_gate.service import PROFILE_PUBLISH, run
from stars.publish_gate.skill import build_skill
from stars.write_authority_check.contract import POLICY_EXPLICIT_PATHS
from stars.write_authority_check.service import grant_digest

PATHS = ["docs/readme.md"]
DIGEST = grant_digest(POLICY_EXPLICIT_PATHS, PATHS)
MANIFEST = "a" * 64


def _prior_envelope(**payload_overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "constellation": "orrery/authorized-content-patch",
        "disposition": "authorized",
        "chain": "signed-envelope-chain",
        "policy_digest": "sha256:test-prior",
        "release": {
            "digest": "sha256:authorized-content-patch…",
            "key_id": "orrery-authorized-content-patch-1",
        },
        "stages": {
            "manifest-bind": {"manifest_digest": MANIFEST},
            "write-authority-check": {"authorized": True},
            "patch-capture": {
                "patch_digest": "b" * 64,
                "changed_paths": list(PATHS),
            },
        },
        "components": [],
        "limitations": [],
        "live_at_call": False,
    }
    payload.update(payload_overrides)
    return {
        "payload": payload,
        "skill": "authorized-content-patch",
        "version": "0.1.0",
        "tool": "run",
        "nonce": "test-publish-gate-1",
        "input_digest": "c" * 64,
        "signature": "d" * 128,
        "key_id": "orrery-authorized-content-patch-1",
        "alg": "Ed25519",
    }


def _authority(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "profile": PROFILE_PUBLISH,
        "policy": POLICY_EXPLICIT_PATHS,
        "allowed_paths": list(PATHS),
        "grant_digest": DIGEST,
    }
    base.update(overrides)
    return base


@pytest.mark.issue(216)
def test_released_over_valid_prior_and_publish_grant() -> None:
    result = run(_prior_envelope(), _authority())
    assert result["constellation"] == "orrery/publish-gate"
    assert result["disposition"] == "released"
    assert result["chain"] == "signed-envelope-chain"
    assert result["policy_digest"].startswith("sha256:")
    assert {"digest", "key_id"} <= set(result["release"])
    assert result["two_phase"] == {
        "edit": "orrery/authorized-content-patch",
        "publish": "orrery/publish-gate",
    }
    stages = result["stages"]
    assert stages["prior-artifact"]["valid"] is True
    assert stages["write-authority-check"]["authorized"] is True
    assert stages["human-witness"]["status"] == "skipped"
    assert any("deploy" in item.lower() for item in result["limitations"])
    assert any("two-phase" in item.lower() for item in result["limitations"])


@pytest.mark.issue(216)
def test_inconclusive_without_valid_prior_envelope() -> None:
    result = run(None, _authority())  # type: ignore[arg-type]
    assert result["disposition"] == "inconclusive"
    assert result["stages"]["prior-artifact"]["error"] == "prior_envelope_invalid"


@pytest.mark.issue(216)
def test_inconclusive_when_prior_not_authorized() -> None:
    result = run(_prior_envelope(disposition="denied"), _authority())
    assert result["disposition"] == "inconclusive"
    assert result["stages"]["prior-artifact"]["error"] == "prior_disposition_invalid"


@pytest.mark.issue(216)
def test_denied_when_publish_grant_mismatches() -> None:
    result = run(_prior_envelope(), _authority(grant_digest="b" * 64))
    assert result["disposition"] == "denied"
    assert "grant_digest_mismatch" in result["stages"]["write-authority-check"]["codes"]


@pytest.mark.issue(216)
def test_inconclusive_when_edit_profile_used() -> None:
    result = run(_prior_envelope(), _authority(profile="edit"))
    assert result["disposition"] == "inconclusive"
    assert (
        result["stages"]["write-authority-check"]["error"] == "publish_profile_required"
    )


@pytest.mark.issue(216)
def test_awaiting_witness_when_required_and_missing() -> None:
    result = run(_prior_envelope(), _authority(), require_witness=True)
    assert result["disposition"] == "awaiting_witness"
    assert result["stages"]["human-witness"]["status"] == "awaiting"
    assert result["stages"]["human-witness"]["mode"] == "awaiting_witness"


@pytest.mark.issue(216)
def test_agent_card_two_phase_and_subtree_contract() -> None:
    card = require_card("orrery/publish-gate")
    assert card.write_authority == "read-only"
    assert card.dispositions == PUBLISH_GATE_DISPOSITIONS
    payload = card.as_dict()
    assert "subtree_contract" in payload
    assert any("two-phase" in item.lower() or "edit" in item.lower() for item in card.use_when)
    assert any(
        "git push" in item.lower() or "deploy" in item.lower() for item in card.not_for
    )
    contract = payload["subtree_contract"]
    pause = contract["pause_policy"]
    assert pause["allowed"] is True
    assert pause["modes"] == ["awaiting_witness"]
    assert "continue_run" in pause["continuation_tools"]
    assert contract["lease_rule"] == "waiting_never_holds_worker_lease"
    stage_ids = [stage["id"] for stage in contract["stages"]]
    assert stage_ids == [
        "prior-artifact",
        "write-authority-check",
        "human-witness",
        "artifact-seal",
    ]
    roles = {stage["id"]: stage["role"] for stage in contract["stages"]}
    assert roles["human-witness"] == "witness"
    assert roles["artifact-seal"] == "composite"
    refs = [stage.get("star_ref") for stage in contract["stages"] if stage.get("star_ref")]
    assert refs == ["orrery/write-authority-check"]
    assert contract["composite_receipt_fields"]["disposition"] == list(
        PUBLISH_GATE_DISPOSITIONS
    )
    summary = (card.graph_summary or "").lower()
    assert "prior-artifact" in summary
    assert "write-authority" in summary


@pytest.mark.issue(216)
def test_registry_policy_and_signed_skill() -> None:
    registry = builtin_registry()
    definition = registry.get("orrery/publish-gate")
    assert definition.kind == "constellation"
    assert definition.direct_mcp_path == "/constellations/publish-gate/mcp"
    assert definition.tools == ("run",)
    graph = policy_for("orrery/publish-gate")
    assert graph is not None
    assert [node.id for node in graph.nodes] == [
        "prior-artifact",
        "write-authority-check",
        "human-witness",
        "artifact-seal",
    ]
    assert [node.star_ref for node in graph.nodes if node.star_ref] == [
        "orrery/write-authority-check",
    ]
    record = next(
        record
        for record in build_star_records(registry, build_direct_skills(registry))
        if record.name == "orrery/publish-gate"
    )
    assert record.kind == "constellation" and record.tools == ("run",)


@pytest.mark.issue(216)
def test_envelope_signs_and_verifies(monkeypatch: pytest.MonkeyPatch) -> None:
    private = Ed25519PrivateKey.generate()
    monkeypatch.setenv("ORRERY_STAR_PRIVATE_KEY", private.private_bytes_raw().hex())
    monkeypatch.setenv("ORRERY_STAR_KEY_ID", "stars-2026-08")
    skill = build_skill()
    envelope = next(item for item in skill._pending if item.name == "run").handler(
        prior_envelope=_prior_envelope(),
        authority=_authority(),
        prior_public_key=None,
        require_witness=False,
    )
    assert envelope.signature
    assert envelope.payload["constellation"] == "orrery/publish-gate"
    assert envelope.payload["disposition"] == "released"
    verify_envelope_wire(envelope.to_wire())
