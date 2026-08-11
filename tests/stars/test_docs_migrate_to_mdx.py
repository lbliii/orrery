"""Tests for orrery/docs-migrate-to-mdx constellation (#178)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from catalog.agent_card import DOCS_MIGRATE_TO_MDX_DISPOSITIONS, require_card
from catalog.constellation import policy_for
from catalog.constellation_run import reset_run_store
from catalog.sync import build_star_records
from stars.builtins import build_direct_skills, builtin_registry
from stars.docs_migrate_to_mdx.fixtures import SAFE_TREE, UNSUPPORTED_TREE
from stars.docs_migrate_to_mdx.service import continue_run, run, status
from stars.docs_migrate_to_mdx.skill import build_skill

_PROFILE_PATH = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "migration"
    / "profiles"
    / "docs_myst_to_mdx_baseline.json"
)


@pytest.fixture(autouse=True)
def _clean_store() -> None:
    reset_run_store()


@pytest.fixture
def signing_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


@pytest.fixture
def baseline_profile() -> dict[str, object]:
    return json.loads(_PROFILE_PATH.read_text(encoding="utf-8"))


def _run_kwargs(key: Ed25519PrivateKey) -> dict[str, object]:
    return {
        "skill_name": "docs-migrate-to-mdx",
        "skill_version": "0.1.0",
        "key_id": "test-docs-migrate-to-mdx",
        "private_key": key,
        "caller_id": "test-caller-178",
    }


@pytest.mark.issue(178)
def test_safe_tree_completes_without_pause(
    signing_key: Ed25519PrivateKey,
    baseline_profile: dict[str, object],
) -> None:
    completed = run(SAFE_TREE, baseline_profile, **_run_kwargs(signing_key))
    assert completed["constellation"] == "orrery/docs-migrate-to-mdx"
    assert completed["disposition"] == "completed"
    assert completed.get("outstanding_action_requests", []) == []
    assert completed["validation_passed"] is True
    assert completed["migration_receipt"]["profile_digest"] == baseline_profile["profile_digest"]
    assert completed["migration_receipt"]["source_manifest_digest"]
    assert completed["output_manifest_digest"]
    assert completed["lease_held"] is False

    terminal = status(completed["run_id"])
    assert terminal["disposition"] == "completed"
    assert terminal["artifact_digest"] == completed["artifact_digest"]


@pytest.mark.issue(178)
def test_unsupported_tree_pauses_with_exact_action_request(
    signing_key: Ed25519PrivateKey,
    baseline_profile: dict[str, object],
) -> None:
    started = run(UNSUPPORTED_TREE, baseline_profile, **_run_kwargs(signing_key))
    assert started["disposition"] == "awaiting_input"
    assert started["graph_position"] == "unsupported-decision"
    assert started["lease_held"] is False
    assert len(started["outstanding_action_requests"]) == 1

    action = started["outstanding_action_requests"][0]
    assert action["kind"] == "unsupported_semantics_decision"
    assert action["schema"]["required"] == ["decisions"]
    assert started["run_id"] == action["run_id"]

    paused = status(started["run_id"])
    assert paused["outstanding_action_requests"][0]["request_id"] == action["request_id"]


@pytest.mark.issue(178)
def test_continue_run_resumes_from_checkpoint(
    signing_key: Ed25519PrivateKey,
    baseline_profile: dict[str, object],
) -> None:
    started = run(UNSUPPORTED_TREE, baseline_profile, **_run_kwargs(signing_key))
    request_id = started["outstanding_action_requests"][0]["request_id"]
    response = {
        "decisions": [
            {"feature_id": "myst.directive.include", "action": "hold"},
            {"feature_id": "myst.ref.include", "action": "hold"},
            {"feature_id": "myst.role.math", "action": "hold"},
        ]
    }

    completed = continue_run(
        started["run_id"],
        request_id,
        response,
        **_run_kwargs(signing_key),
    )
    assert completed["disposition"] == "completed"
    assert completed["validation_digest"]
    assert completed["cites"]
    assert len(completed["cites"]) == 3

    terminal = status(started["run_id"])
    assert terminal["disposition"] == "completed"
    assert terminal["outstanding_action_requests"] == []


@pytest.mark.issue(178)
def test_duplicate_continue_run_replays_same_composite(
    signing_key: Ed25519PrivateKey,
    baseline_profile: dict[str, object],
) -> None:
    started = run(UNSUPPORTED_TREE, baseline_profile, **_run_kwargs(signing_key))
    request_id = started["outstanding_action_requests"][0]["request_id"]
    response = {
        "decisions": [
            {"feature_id": "myst.directive.include", "action": "hold"},
            {"feature_id": "myst.ref.include", "action": "hold"},
            {"feature_id": "myst.role.math", "action": "hold"},
        ]
    }

    first = continue_run(
        started["run_id"],
        request_id,
        response,
        **_run_kwargs(signing_key),
    )
    second = continue_run(
        started["run_id"],
        request_id,
        response,
        **_run_kwargs(signing_key),
    )

    assert first["artifact_digest"] == second["artifact_digest"]
    assert second.get("replayed") is True
    assert first["bundle_digest"] == second["bundle_digest"]


@pytest.mark.issue(178)
def test_late_incompatible_response_replays_without_second_patch(
    signing_key: Ed25519PrivateKey,
    baseline_profile: dict[str, object],
) -> None:
    started = run(UNSUPPORTED_TREE, baseline_profile, **_run_kwargs(signing_key))
    request_id = started["outstanding_action_requests"][0]["request_id"]
    hold_all = {
        "decisions": [
            {"feature_id": "myst.directive.include", "action": "hold"},
            {"feature_id": "myst.ref.include", "action": "hold"},
            {"feature_id": "myst.role.math", "action": "hold"},
        ]
    }
    hold_subset = {
        "decisions": [
            {"feature_id": "myst.directive.include", "action": "hold"},
            {"feature_id": "myst.ref.include", "action": "hold"},
            {"feature_id": "myst.role.math", "action": "abort"},
        ]
    }

    first = continue_run(
        started["run_id"],
        request_id,
        hold_all,
        **_run_kwargs(signing_key),
    )
    assert first["disposition"] == "completed"

    late = continue_run(
        started["run_id"],
        request_id,
        hold_subset,
        **_run_kwargs(signing_key),
    )
    assert late.get("replayed") is True
    assert late["artifact_digest"] == first["artifact_digest"]


@pytest.mark.issue(178)
def test_receipt_binds_digests_without_raw_private_source(
    signing_key: Ed25519PrivateKey,
    baseline_profile: dict[str, object],
) -> None:
    completed = run(SAFE_TREE, baseline_profile, **_run_kwargs(signing_key))
    receipt = completed["migration_receipt"]
    composite = json.dumps(completed)
    assert "source_bytes" not in receipt
    assert "target_bytes" not in receipt
    assert "full_patch_text" not in receipt
    assert '"content":' not in composite
    assert receipt["profile_digest"] == baseline_profile["profile_digest"]
    assert receipt["source_manifest_digest"]
    assert receipt["bundle_digest"]
    assert receipt["validation_digest"]


@pytest.mark.issue(178)
def test_agent_card_subtree_contract() -> None:
    card = require_card("orrery/docs-migrate-to-mdx")
    assert card.dispositions == DOCS_MIGRATE_TO_MDX_DISPOSITIONS
    contract = card.as_dict()["subtree_contract"]
    pause = contract["pause_policy"]
    assert pause["allowed"] is True
    assert pause["modes"] == ["awaiting_input"]
    assert "continue_run" in pause["continuation_tools"]
    assert contract["lease_rule"] == "waiting_never_holds_worker_lease"
    stage_ids = [stage["id"] for stage in contract["stages"]]
    assert stage_ids == [
        "inventory",
        "choose-profile",
        "safe-convert",
        "unsupported-decision",
        "validate-diff",
        "artifact-seal",
    ]


@pytest.mark.issue(178)
def test_registry_policy_and_signed_skill() -> None:
    registry = builtin_registry()
    definition = registry.get("orrery/docs-migrate-to-mdx")
    assert definition.kind == "constellation"
    assert definition.direct_mcp_path == "/constellations/docs-migrate-to-mdx/mcp"
    assert definition.tools == ("run", "status", "continue_run", "cancel")
    graph = policy_for("orrery/docs-migrate-to-mdx")
    assert graph is not None
    assert [node.id for node in graph.nodes] == [
        "inventory",
        "choose-profile",
        "safe-convert",
        "unsupported-decision",
        "validate-diff",
        "artifact-seal",
    ]
    record = next(
        record
        for record in build_star_records(registry, build_direct_skills(registry))
        if record.name == "orrery/docs-migrate-to-mdx"
    )
    assert record.kind == "constellation"

    skill = build_skill(private_key=Ed25519PrivateKey.generate())
    assert {item.name for item in skill._pending} == {
        "run",
        "status",
        "continue_run",
        "cancel",
    }
