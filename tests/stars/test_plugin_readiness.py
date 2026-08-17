"""Tests for orrery/plugin-readiness constellation (#536)."""

from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from catalog.agent_card import PLUGIN_READINESS_DISPOSITIONS, require_card
from catalog.constellation import policy_for
from catalog.sync import build_star_records
from dogfood import verify_receipt as verify_envelope_wire
from stars.builtins import build_direct_skills, builtin_registry
from stars.plugin_preflight.contract import PLUGIN_SCHEMA_ID
from stars.plugin_readiness.service import run
from stars.plugin_readiness.skill import build_skill

ROOT = Path(__file__).resolve().parents[2]


def _orrery_bundle() -> list[dict[str, str]]:
    package = ROOT / "plugins" / "orrery"
    return [
        {"path": path.name, "content": path.read_text(encoding="utf-8")}
        for path in sorted(package.iterdir())
        if path.is_file()
    ]


@pytest.mark.issue(536)
def test_conformant_over_official_orrery_package() -> None:
    result = run(_orrery_bundle())
    assert result["constellation"] == "orrery/plugin-readiness"
    assert result["disposition"] == "conformant"
    assert result["chain"] == "signed-envelope-chain"
    assert result["policy_digest"].startswith("sha256:")
    stages = result["stages"]
    assert stages["plugin-preflight"]["passed"] is True
    assert stages["structure-audit"]["skipped"] is True
    assert stages["structure-audit"]["passed"] is True
    assert result["stages"]["manifest-bind"]["manifest_digest"]


@pytest.mark.issue(536)
def test_needs_work_when_plugin_json_missing() -> None:
    result = run([{"path": "README.md", "content": "hi\n"}])
    assert result["disposition"] == "needs-work"
    assert result["stages"]["plugin-preflight"]["passed"] is False


@pytest.mark.issue(536)
def test_inconclusive_on_invalid_bundle() -> None:
    result = run(None)  # type: ignore[arg-type]
    assert result["disposition"] == "inconclusive"
    assert result["stages"]["bundle"]["error"] == "files_invalid"


@pytest.mark.issue(536)
def test_agent_card_subtree_contract_sync_only() -> None:
    card = require_card("orrery/plugin-readiness")
    assert card.write_authority == "read-only"
    assert card.dispositions == PLUGIN_READINESS_DISPOSITIONS
    contract = card.as_dict()["subtree_contract"]
    assert contract["pause_policy"]["allowed"] is False
    assert contract["lease_rule"] == "waiting_never_holds_worker_lease"
    stage_ids = [stage["id"] for stage in contract["stages"]]
    assert stage_ids == [
        "manifest-bind",
        "plugin-preflight",
        "structure-audit",
        "artifact-seal",
    ]
    assert contract["composite_receipt_fields"]["disposition"] == list(
        PLUGIN_READINESS_DISPOSITIONS
    )


@pytest.mark.issue(536)
def test_registry_policy_and_signed_skill() -> None:
    registry = builtin_registry()
    definition = registry.get("orrery/plugin-readiness")
    assert definition.kind == "constellation"
    assert definition.direct_mcp_path == "/constellations/plugin-readiness/mcp"
    assert definition.tools == ("run",)
    graph = policy_for("orrery/plugin-readiness")
    assert graph is not None
    assert [node.star_ref for node in graph.nodes if node.star_ref] == [
        "orrery/manifest-bind",
        "orrery/plugin-preflight",
        "orrery/structure-audit",
    ]
    record = next(
        record
        for record in build_star_records(registry, build_direct_skills(registry))
        if record.name == "orrery/plugin-readiness"
    )
    assert record.kind == "constellation" and record.tools == ("run",)


@pytest.mark.issue(536)
def test_envelope_signs_and_verifies(monkeypatch: pytest.MonkeyPatch) -> None:
    private = Ed25519PrivateKey.generate()
    monkeypatch.setenv("ORRERY_STAR_PRIVATE_KEY", private.private_bytes_raw().hex())
    monkeypatch.setenv("ORRERY_STAR_KEY_ID", "stars-2026-08")
    skill = build_skill()
    envelope = next(item for item in skill._pending if item.name == "run").handler(
        files=[
            {
                "path": "plugin.json",
                "content": (
                    f'{{"$schema": "{PLUGIN_SCHEMA_ID}", "name": "minimal-plugin"}}'
                ),
            }
        ],
    )
    assert envelope.signature
    assert envelope.payload["constellation"] == "orrery/plugin-readiness"
    assert envelope.payload["disposition"] == "conformant"
    verify_envelope_wire(envelope.to_wire())
