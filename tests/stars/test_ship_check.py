"""Tests for orrery/ship-check dual-mode constellation (#214)."""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from catalog.agent_card import require_card
from catalog.constellation import policy_for
from dogfood import verify_receipt as verify_envelope_wire
from stars.builtins import builtin_registry
from stars.ship_check.service import MODE_CONTENT_BUNDLE, MODE_METADATA, run
from stars.ship_check.skill import build_skill

CLEAN_BUNDLE = [
    {
        "path": "docs/readme.md",
        "content": (
            "---\ntitle: Readme\n---\n\n# Readme\n\n"
            "See [Python](https://docs.python.org/3/).\n"
        ),
    }
]


def _ok_transport(url: str, *, timeout: float) -> tuple[str, int]:
    return url, 200


@pytest.mark.issue(214)
def test_complete_and_incomplete_component_paths() -> None:
    ok = run(
        "httpx",
        "sha256:old",
        package_provider=lambda _: {"version": "1", "source_digest": "sha256:p"},
        source_provider=lambda _: {"status": "unchanged", "current_digest": "sha256:s"},
        world_time_provider=lambda: {"datetime": "2026-01-01T00:00:00Z", "source": "fixture"},
    )
    assert ok["mode"] == MODE_METADATA
    assert ok["verdict"] == "ready_to_reason" and ok["source_watch"]["status"] == "unchanged"
    assert ok["disposition"] == "ready"
    assert ok["chain"] == "signed-envelope-chain"
    assert ok["policy_digest"].startswith("sha256:")
    assert {"digest", "key_id"} <= set(ok["release"])
    assert set(ok["stages"]) == {"release", "source-watch", "world-time"}
    bad = run(
        "zod",
        package_provider=lambda _: {"error": "down"},
        source_provider=lambda _: {"status": "changed"},
    )
    assert bad["verdict"] == "incomplete" and bad["disposition"] == "not-ready"
    time_bad = run(
        "httpx",
        package_provider=lambda _: {},
        source_provider=lambda _: {},
        world_time_provider=lambda: {"error": "offline"},
    )
    assert time_bad["verdict"] == "incomplete" and time_bad["utc"]["error"] == "offline"


@pytest.mark.issue(214)
def test_content_bundle_reuses_readiness_stages() -> None:
    result = run(
        mode=MODE_CONTENT_BUNDLE,
        files=CLEAN_BUNDLE,
        link_transport=_ok_transport,
    )
    assert result["constellation"] == "orrery/ship-check"
    assert result["mode"] == MODE_CONTENT_BUNDLE
    assert result["disposition"] == "ready"
    assert result["chain"] == "signed-envelope-chain"
    stages = result["stages"]
    assert stages["manifest-preflight"]["passed"] is True
    assert stages["structure-audit"]["passed"] is True
    assert stages["link-check-bounded"]["passed"] is True
    assert "verdict" not in result


@pytest.mark.issue(214)
def test_content_bundle_inconclusive_on_invalid_files() -> None:
    result = run(mode=MODE_CONTENT_BUNDLE, files=None)
    assert result["disposition"] == "inconclusive"
    assert result["stages"]["bundle"]["error"] == "files_invalid"


@pytest.mark.issue(214)
def test_invalid_mode() -> None:
    result = run("httpx", mode="deploy")
    assert result["disposition"] == "inconclusive"
    assert result["stages"]["mode"]["error"] == "mode_invalid"


@pytest.mark.issue(214)
def test_agent_card_documents_both_modes_and_subtree_contract() -> None:
    card = require_card("orrery/ship-check")
    payload = card.as_dict()
    assert "subtree_contract" in payload
    contract = payload["subtree_contract"]
    assert contract["pause_policy"]["allowed"] is False
    assert contract["lease_rule"] == "waiting_never_holds_worker_lease"
    stage_ids = [stage["id"] for stage in contract["stages"]]
    assert stage_ids == [
        "release",
        "source-watch",
        "world-time",
        "manifest-bind",
        "manifest-preflight",
        "structure-audit",
        "link-check-bounded",
        "artifact-seal",
    ]
    assert contract["stages"][-1]["role"] == "composite"
    assert "star_ref" not in contract["stages"][-1]
    optional = {stage["id"] for stage in contract["stages"] if stage.get("optional")}
    assert "release" in optional and "manifest-bind" in optional
    assert "artifact-seal" not in optional
    run_contract = payload["run_contract"]
    assert "mode" in run_contract["optional_inputs"]
    assert "files" in run_contract["optional_inputs"]
    assert "metadata" in run_contract["input_bundle"]["mode"]["note"]
    assert "content-bundle" in run_contract["input_bundle"]["mode"]["note"]
    assert "mode=metadata" in payload["graph_summary"]
    assert "mode=content-bundle" in payload["graph_summary"]
    assert "content-bundle" in payload["summary"]


@pytest.mark.issue(214)
def test_registry_constellation_and_skill() -> None:
    definition = builtin_registry().get("orrery/ship-check")
    assert (
        definition.kind == "constellation"
        and definition.direct_mcp_path == "/constellations/ship-check/mcp"
    )
    assert {item.name for item in build_skill()._pending} == {"run"}
    graph = policy_for("orrery/ship-check")
    assert graph is not None
    node_ids = {node.id for node in graph.nodes}
    assert {"release", "manifest-bind", "artifact-seal"} <= node_ids


@pytest.mark.issue(214)
def test_envelope_signs_metadata_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    private = Ed25519PrivateKey.generate()
    monkeypatch.setenv("ORRERY_STAR_PRIVATE_KEY", private.private_bytes_raw().hex())
    monkeypatch.setenv("ORRERY_STAR_KEY_ID", "stars-2026-08")
    skill = build_skill()
    # Avoid live egress: exercise signed path with content-bundle fixture transport
    # is not available via skill; metadata path needs providers. Call service seal
    # fields through skill with a stubbed service for envelope shape.
    import stars.ship_check.skill as ship_mod

    ship_mod.run_check = lambda package, digest="": {  # type: ignore[assignment]
        "constellation": "orrery/ship-check",
        "mode": MODE_METADATA,
        "verdict": "ready_to_reason",
        "disposition": "ready",
        "chain": "signed-envelope-chain",
        "package": package,
        "source_digest": digest,
    }
    envelope = next(item for item in skill._pending if item.name == "run").handler(
        package="httpx",
        source_digest="sha256:old",
    )
    assert envelope.signature
    assert envelope.payload["constellation"] == "orrery/ship-check"
    assert envelope.payload["verdict"] == "ready_to_reason"
    verify_envelope_wire(envelope.to_wire())
