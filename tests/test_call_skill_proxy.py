"""Aggregate ``/mcp`` call_skill same-origin forwarder (ADR 0010, #417)."""

from __future__ import annotations

import json
import sys
from typing import Any

import pytest
from chirp.skill import verify_envelope
from chirp.testing import TestClient

from catalog.call_skill_proxy import (
    forward_call_skill,
    is_same_origin_catalog_endpoint,
    mcp_endpoint_path,
)
from discovery import MCP_TOOLS_ALLOWLIST, MCP_TOOLS_DENYLIST
from dogfood import envelope_from_wire

_META_PROTOCOL_VERSION = "io.modelcontextprotocol/protocolVersion"


def _modern_mcp_params(**extra: Any) -> dict[str, Any]:
    params: dict[str, Any] = {
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


@pytest.mark.issue(417)
def test_mcp_endpoint_path_parses_skill_dns() -> None:
    assert mcp_endpoint_path("mcp://orrery.lol/constellations/stale-proof/mcp") == (
        "/constellations/stale-proof/mcp"
    )


@pytest.mark.issue(417)
def test_same_origin_catalog_endpoint_accepts_apex_and_tenant() -> None:
    assert is_same_origin_catalog_endpoint("mcp://orrery.lol/stars/world-time/mcp")
    assert is_same_origin_catalog_endpoint("mcp://acme.orrery.lol/s/release-gate")
    assert not is_same_origin_catalog_endpoint("mcp://other.example/stars/world-time/mcp")
    assert not is_same_origin_catalog_endpoint("https://orrery.lol/mcp")


@pytest.mark.issue(417)
@pytest.mark.asyncio
async def test_call_skill_stale_proof_run_returns_json_envelope(example_app) -> None:
    async with TestClient(example_app) as client:
        called = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "id": 417,
                "params": _modern_mcp_params(
                    name="call_skill",
                    arguments={
                        "name": "orrery/stale-proof",
                        "tool": "run",
                        "arguments": {},
                    },
                ),
            },
            headers=_modern_mcp_headers("tools/call", "call_skill"),
        )
        assert called.status == 200
        body = json.loads(json.loads(called.text)["result"]["content"][0]["text"])
        assert body["status"] == "ok"
        assert body["skill"] == "orrery/stale-proof"
        assert body["tool"] == "run"
        payload = body["payload"]
        if "status" not in payload and isinstance(payload.get("payload"), dict):
            payload = payload["payload"]
        proof = payload.get("status") or payload.get("disposition")
        assert proof in {
            "fresh_proof",
            "incomplete",
            "ready",
            "not-ready",
            "stale",
            "blocked",
        }, f"unexpected stale-proof payload keys: {sorted(payload)}"
        wire = body["envelope_wire"]
        assert wire["tool"] == "run"
        app_module = sys.modules["orrery_app_under_test"]
        skill = app_module.direct_star_skills["orrery/stale-proof"]
        assert verify_envelope(envelope_from_wire(wire), skill.public_key) is True


@pytest.mark.issue(417)
@pytest.mark.asyncio
async def test_call_skill_unknown_name_returns_not_found(example_app) -> None:
    async with TestClient(example_app) as client:
        called = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "id": 418,
                "params": _modern_mcp_params(
                    name="call_skill",
                    arguments={
                        "name": "orrery/no-such-skill",
                        "tool": "run",
                        "arguments": {},
                    },
                ),
            },
            headers=_modern_mcp_headers("tools/call", "call_skill"),
        )
        assert called.status == 200
        body = json.loads(json.loads(called.text)["result"]["content"][0]["text"])
        assert body["status"] == "error"
        assert body["error"]["code"] == "not_found"


@pytest.mark.issue(417)
@pytest.mark.asyncio
async def test_call_skill_unknown_tool_returns_unknown_tool(example_app) -> None:
    async with TestClient(example_app) as client:
        called = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "id": 419,
                "params": _modern_mcp_params(
                    name="call_skill",
                    arguments={
                        "name": "orrery/stale-proof",
                        "tool": "convert",
                        "arguments": {},
                    },
                ),
            },
            headers=_modern_mcp_headers("tools/call", "call_skill"),
        )
        assert called.status == 200
        body = json.loads(json.loads(called.text)["result"]["content"][0]["text"])
        assert body["status"] == "error"
        assert body["error"]["code"] == "unknown_tool"


@pytest.mark.issue(417)
@pytest.mark.asyncio
async def test_default_mcp_tools_list_includes_call_skill_not_run(example_app) -> None:
    async with TestClient(example_app) as client:
        listed = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": 420,
                "params": _modern_mcp_params(),
            },
            headers=_modern_mcp_headers("tools/list"),
        )
        assert listed.status == 200
        names = {t["name"] for t in json.loads(listed.text)["result"]["tools"]}
        assert names == MCP_TOOLS_ALLOWLIST
        assert "call_skill" in names
        assert names.isdisjoint(MCP_TOOLS_DENYLIST)
        for denied in ("run", "convert", "fetch"):
            assert denied in MCP_TOOLS_DENYLIST
            assert denied not in names


@pytest.mark.issue(417)
@pytest.mark.asyncio
async def test_forward_call_skill_off_origin_returns_publisher_direct_required(
    example_app,
) -> None:
    result = await forward_call_skill(
        example_app,
        name="acme/release-gate",
        tool="run",
        arguments={},
    )
    assert result["status"] == "error"
    assert result["error"]["code"] == "publisher_direct_required"
