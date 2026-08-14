"""Host-level MCP connect matrix sharing the public-domain canary fixtures (#389)."""

from __future__ import annotations

import json

import pytest
from chirp.testing import TestClient

from discovery import MCP_PROTOCOL_VERSION
from scripts.canary_public_domain import (
    FORBIDDEN_PROTOCOL_VERSION,
    LEGACY_CLIENT_FIXTURES,
    MCP_CONNECT_DEFAULT,
    initialize_rpc,
    tools_list_rpc,
)


@pytest.mark.issue(389)
def test_shared_fixtures_match_discovery_default() -> None:
    assert MCP_CONNECT_DEFAULT == MCP_PROTOCOL_VERSION
    assert FORBIDDEN_PROTOCOL_VERSION not in LEGACY_CLIENT_FIXTURES
    assert LEGACY_CLIENT_FIXTURES == ("2025-11-25", "2025-06-18")


@pytest.mark.issue(389)
async def test_server_card_protocol_version_matches_discovery(example_app) -> None:
    async with TestClient(example_app) as client:
        response = await client.get("/.well-known/mcp/server-card.json")
        assert response.status == 200
        card = json.loads(response.text)
        assert card["protocolVersion"] == MCP_PROTOCOL_VERSION
        assert card["protocolVersion"] == MCP_CONNECT_DEFAULT


@pytest.mark.issue(389)
@pytest.mark.parametrize("client_version", LEGACY_CLIENT_FIXTURES)
async def test_mcp_legacy_initialize_matrix(example_app, client_version: str) -> None:
    async with TestClient(example_app) as client:
        initialized = await client.post(
            "/mcp",
            json=initialize_rpc(client_version, request_id=389),
            headers={
                "content-type": "application/json",
                "mcp-protocol-version": client_version,
            },
        )
        assert initialized.status == 200
        version = json.loads(initialized.text)["result"]["protocolVersion"]
        assert version == client_version
        assert version != FORBIDDEN_PROTOCOL_VERSION

        listed = await client.post(
            "/mcp",
            json=tools_list_rpc(request_id=390),
            headers={
                "content-type": "application/json",
                "mcp-protocol-version": client_version,
            },
        )
        assert listed.status == 200
        tool_names = {tool["name"] for tool in json.loads(listed.text)["result"]["tools"]}
        assert "gaze_match" in tool_names
