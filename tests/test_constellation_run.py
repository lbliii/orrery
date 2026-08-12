"""Tests for constellation run checkpoint store (#152 / #154)."""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from catalog.constellation_run import (
    ActionRequest,
    CheckpointRecord,
    ConstellationRunError,
    ConstellationRunStore,
    cancel_checkpoint,
    checkpoint_status_payload,
    get_run_store,
    payload_digest_for,
    reset_run_store,
    run_constellation,
    status_for_run,
)
from stars._core.attribution import PAYLOAD_VIA


@pytest.fixture(autouse=True)
def _clean_store() -> None:
    reset_run_store()


@pytest.mark.issue(154)
def test_checkpoint_status_exposes_action_request_and_no_lease() -> None:
    store = get_run_store()
    action = ActionRequest(
        request_id="req-1",
        run_id="run-1",
        kind="audience_recommendation_choice",
        schema={"type": "object"},
        audience="decision_maker",
        expires_at="2099-01-01T00:00:00+00:00",
    )
    record = CheckpointRecord(
        run_id="run-1",
        caller_id="caller-a",
        constellation="orrery/board-memo",
        disposition="awaiting_input",
        policy_digest="sha256:" + "a" * 64,
        release={"digest": "sha256:board-memo…", "key_id": "orrery-board-memo-1"},
        graph_position="audience-choice",
        stage_receipt_digests=("b" * 64,),
        outstanding_action_requests=(action,),
        bundle={"title": "T", "summary": "S"},
        lease_held=False,
    )
    store.put_checkpoint(record)

    status = checkpoint_status_payload(record)
    assert status["disposition"] == "awaiting_input"
    assert status["lease_held"] is False
    assert status["lease_rule"] == "waiting_never_holds_worker_lease"
    assert len(status["outstanding_action_requests"]) == 1
    assert status["outstanding_action_requests"][0]["request_id"] == "req-1"


@pytest.mark.issue(154)
def test_seal_continuation_replays_same_result() -> None:
    store = ConstellationRunStore()
    payload = {"audience": "board", "recommendation": "approve"}
    calls = {"count": 0}

    def producer() -> dict[str, str]:
        calls["count"] += 1
        return {"artifact_digest": "c" * 64, "disposition": "completed"}

    first = store.seal_continuation(
        caller_id="caller-a",
        run_id="run-1",
        request_id="req-1",
        payload=payload,
        producer=producer,
    )
    second = store.seal_continuation(
        caller_id="caller-a",
        run_id="run-1",
        request_id="req-1",
        payload=payload,
        producer=producer,
    )

    assert calls["count"] == 1
    assert first["artifact_digest"] == second["artifact_digest"]
    assert second.get("replayed") is True


@pytest.mark.issue(154)
def test_seal_continuation_rejects_incompatible_replay() -> None:
    store = ConstellationRunStore()

    store.seal_continuation(
        caller_id="caller-a",
        run_id="run-1",
        request_id="req-1",
        payload={"audience": "board", "recommendation": "approve"},
        producer=lambda: {"artifact_digest": "a" * 64},
    )

    with pytest.raises(ConstellationRunError, match="replay_incompatible"):
        store.seal_continuation(
            caller_id="caller-a",
            run_id="run-1",
            request_id="req-1",
            payload={"audience": "board", "recommendation": "revise"},
            producer=lambda: {"artifact_digest": "b" * 64},
        )


@pytest.mark.issue(154)
def test_payload_digest_is_stable() -> None:
    first = payload_digest_for({"audience": "board", "recommendation": "approve"})
    second = payload_digest_for({"recommendation": "approve", "audience": "board"})
    assert first == second


@pytest.mark.issue(154)
def test_cancel_checkpoint_terminalizes_waiting_run() -> None:
    store = get_run_store()
    record = CheckpointRecord(
        run_id="run-cancel",
        caller_id="caller-a",
        constellation="orrery/board-memo",
        disposition="awaiting_input",
        policy_digest="sha256:" + "d" * 64,
        release={"digest": "sha256:board-memo…", "key_id": "orrery-board-memo-1"},
        graph_position="audience-choice",
        stage_receipt_digests=("e" * 64,),
        outstanding_action_requests=(
            ActionRequest(
                request_id="req-1",
                run_id="run-cancel",
                kind="audience_recommendation_choice",
                schema={},
                audience="decision_maker",
                expires_at="2099-01-01T00:00:00+00:00",
            ),
        ),
        lease_held=False,
    )
    store.put_checkpoint(record)

    result = cancel_checkpoint("run-cancel", caller_id="caller-a")
    assert result["disposition"] == "cancelled"
    assert result["outstanding_action_requests"] == []
    assert result["lease_held"] is False


@pytest.mark.issue(245)
def test_sync_run_constellation_still_works_via_store() -> None:
    key = Ed25519PrivateKey.generate()
    result = run_constellation(
        {"pages": ["README.md"], "links": [], "examples": []},
        constellation="orrery/stale-proof",
        skill_name="launch-gate",
        skill_version="2.0.0",
        key_id="test-sync",
        private_key=key,
    )
    assert result["status"] == "completed"
    assert result["via"] == PAYLOAD_VIA
    status = status_for_run(result["run_id"])
    assert status["run_id"] == result["run_id"]
    assert status["via"] == PAYLOAD_VIA
