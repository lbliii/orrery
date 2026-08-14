"""Tests for orrery/board-memo resumable constellation (#154)."""

from __future__ import annotations

import base64
import json

import pytest
from chirp.testing import TestClient
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from catalog.agent_card import BOARD_MEMO_DISPOSITIONS, require_card
from catalog.constellation import policy_for
from catalog.constellation_run import reset_run_store
from catalog.sync import build_star_records
from stars.board_memo.service import cancel, continue_run, run, status
from stars.board_memo.skill import build_skill
from stars.builtins import build_direct_skills, builtin_registry

_META_PROTOCOL_VERSION = "io.modelcontextprotocol/protocolVersion"


def _modern_mcp_params(**extra: object) -> dict[str, object]:
    params: dict[str, object] = {
        "_meta": {
            _META_PROTOCOL_VERSION: "2026-07-28",
            "io.modelcontextprotocol/clientCapabilities": {},
        },
    }
    params.update(extra)
    return params


def _modern_mcp_headers(method: str, name: str | None = None) -> dict[str, str]:
    headers = {
        "content-type": "application/json",
        "mcp-protocol-version": "2026-07-28",
        "mcp-method": method,
    }
    if name is not None:
        headers["mcp-name"] = name
    return headers


def _mcp_tool_body(response_text: str) -> dict[str, object]:
    return json.loads(json.loads(response_text)["result"]["content"][0]["text"])


@pytest.fixture(autouse=True)
def _clean_store() -> None:
    reset_run_store()


@pytest.fixture
def signing_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


def _run_kwargs(key: Ed25519PrivateKey) -> dict[str, object]:
    return {
        "skill_name": "board-memo",
        "skill_version": "0.1.0",
        "key_id": "test-board-memo",
        "private_key": key,
        "caller_id": "test-caller-154",
    }


@pytest.mark.issue(394)
@pytest.mark.asyncio
async def test_board_memo_mcp_run_surfaces_pause_contract(example_app) -> None:
    """Direct MCP ``run`` returns ADR 0010 JSON with pause/resume contract (#394)."""
    async with TestClient(example_app) as client:
        response = await client.post(
            "/constellations/board-memo/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "id": 394,
                "params": _modern_mcp_params(
                    name="run",
                    arguments={
                        "title": "Q3 Platform Update",
                        "summary": "Revenue grew 12% with stable infra costs.",
                        "author": "ops",
                        "caller_id": "test-caller-394",
                    },
                ),
            },
            headers=_modern_mcp_headers("tools/call", "run"),
        )
        assert response.status == 200
        body = _mcp_tool_body(response.text)
        assert body["status"] == "ok"
        assert body["tool"] == "run"
        assert not str(body).startswith("Envelope(")
        assert body["disposition"] == "awaiting_input"
        assert isinstance(body["run_id"], str) and body["run_id"]
        payload = body["payload"]
        assert isinstance(payload, dict)
        assert payload["disposition"] == "awaiting_input"
        requests = body["outstanding_action_requests"]
        assert isinstance(requests, list) and len(requests) == 1
        assert requests[0]["request_id"]
        assert requests[0]["kind"] == "audience_recommendation_choice"
        assert isinstance(requests[0]["schema"], dict)
        assert isinstance(requests[0]["prompt"], str)
        assert payload["outstanding_action_requests"][0]["request_id"] == requests[0]["request_id"]


@pytest.mark.issue(154)
def test_start_pause_status_continue_pdf_path(signing_key: Ed25519PrivateKey) -> None:
    started = run(
        "Q3 Platform Update",
        "Revenue grew 12% with stable infra costs.",
        author="ops",
        **_run_kwargs(signing_key),
    )
    assert started["constellation"] == "orrery/board-memo"
    assert started["disposition"] == "awaiting_input"
    assert started["graph_position"] == "audience-choice"
    assert started["lease_held"] is False
    assert len(started["outstanding_action_requests"]) == 1

    request_id = started["outstanding_action_requests"][0]["request_id"]
    run_id = started["run_id"]

    paused = status(run_id)
    assert paused["disposition"] == "awaiting_input"
    assert len(paused["outstanding_action_requests"]) == 1
    assert paused["outstanding_action_requests"][0]["request_id"] == request_id
    assert paused["lease_held"] is False

    completed = continue_run(
        run_id,
        request_id,
        {"audience": "board", "recommendation": "approve"},
        **_run_kwargs(signing_key),
    )
    assert completed["disposition"] == "completed"
    assert completed["artifact_digest"]
    assert completed["stages"]["pdf-seal"]["page_count"] >= 1
    pdf_bytes = base64.b64decode(str(completed["artifact_base64"]))
    assert pdf_bytes.startswith(b"%PDF")

    terminal = status(run_id)
    assert terminal["disposition"] == "completed"
    assert terminal["artifact_digest"] == completed["artifact_digest"]
    assert terminal["outstanding_action_requests"] == []
    assert terminal["lease_held"] is False


@pytest.mark.issue(154)
def test_duplicate_continue_run_replays_same_composite(signing_key: Ed25519PrivateKey) -> None:
    started = run("Title", "Summary body.", **_run_kwargs(signing_key))
    request_id = started["outstanding_action_requests"][0]["request_id"]
    response = {"audience": "executive", "recommendation": "revise"}

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
    assert first["stage_receipt_digests"] == second["stage_receipt_digests"]


@pytest.mark.issue(154)
def test_waiting_never_holds_worker_lease(signing_key: Ed25519PrivateKey) -> None:
    started = run("Lease check", "Ensure no lease while paused.", **_run_kwargs(signing_key))
    assert started["lease_held"] is False
    assert started["lease_rule"] == "waiting_never_holds_worker_lease"

    paused = status(started["run_id"])
    assert paused["lease_held"] is False


@pytest.mark.issue(154)
def test_cancel_clears_outstanding_request(signing_key: Ed25519PrivateKey) -> None:
    started = run("Cancel me", "Summary.", **_run_kwargs(signing_key))
    result = cancel(started["run_id"], caller_id="test-caller-154")
    assert result["disposition"] == "cancelled"
    assert result["outstanding_action_requests"] == []


@pytest.mark.issue(154)
def test_agent_card_subtree_contract_example_2() -> None:
    card = require_card("orrery/board-memo")
    assert card.dispositions == BOARD_MEMO_DISPOSITIONS
    contract = card.as_dict()["subtree_contract"]
    pause = contract["pause_policy"]
    assert pause["allowed"] is True
    assert pause["modes"] == ["awaiting_input"]
    assert "continue_run" in pause["continuation_tools"]
    assert contract["lease_rule"] == "waiting_never_holds_worker_lease"
    stage_ids = [stage["id"] for stage in contract["stages"]]
    assert stage_ids == ["memo-bind", "audience-choice", "pdf-seal"]
    roles = {stage["id"]: stage["role"] for stage in contract["stages"]}
    assert roles["audience-choice"] == "pause"
    assert roles["pdf-seal"] == "composite"


@pytest.mark.issue(154)
def test_registry_policy_and_signed_skill() -> None:
    registry = builtin_registry()
    definition = registry.get("orrery/board-memo")
    assert definition.kind == "constellation"
    assert definition.direct_mcp_path == "/constellations/board-memo/mcp"
    assert definition.tools == ("run", "status", "continue_run", "cancel")
    graph = policy_for("orrery/board-memo")
    assert graph is not None
    assert [node.id for node in graph.nodes] == [
        "memo-bind",
        "audience-choice",
        "pdf-seal",
    ]
    record = next(
        record
        for record in build_star_records(registry, build_direct_skills(registry))
        if record.name == "orrery/board-memo"
    )
    assert record.kind == "constellation"

    skill = build_skill(private_key=Ed25519PrivateKey.generate())
    assert {item.name for item in skill._pending} == {
        "run",
        "status",
        "continue_run",
        "cancel",
    }
