"""Tests for StandardMcpCompatibilityMiddleware protocol negotiation."""

from __future__ import annotations

import json

import pytest
from chirp.testing import TestClient


def _standard_headers() -> dict[str, str]:
    return {
        "content-type": "application/json",
        "mcp-protocol-version": "2025-06-18",
    }


@pytest.mark.asyncio
async def test_initialize_echoes_standard_protocol_from_header(example_app) -> None:
    async with TestClient(example_app) as client:
        response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": 1,
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "cursor", "version": "1"},
                },
            },
            headers=_standard_headers(),
        )
        assert response.status == 200
        body = json.loads(response.text)
        assert body["result"]["protocolVersion"] == "2025-06-18"
        assert "chirp/legacyOfframp" not in body["result"].get("_meta", {})


@pytest.mark.asyncio
async def test_initialize_echoes_standard_protocol_from_body_only(example_app) -> None:
    """Clients may send ``params.protocolVersion`` before the protocol header."""
    async with TestClient(example_app) as client:
        response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": 2,
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "cursor", "version": "1"},
                },
            },
            headers={"content-type": "application/json"},
        )
        assert response.status == 200
        body = json.loads(response.text)
        assert body["result"]["protocolVersion"] == "2025-06-18"


@pytest.mark.asyncio
async def test_modern_initialize_response_is_unchanged(example_app) -> None:
    async with TestClient(example_app) as client:
        response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": 3,
                "params": {
                    "_meta": {
                        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                    },
                },
            },
            headers={
                "content-type": "application/json",
                "mcp-protocol-version": "2026-07-28",
                "mcp-method": "initialize",
            },
        )
        assert response.status == 200
        body = json.loads(response.text)
        assert body["result"]["protocolVersion"] == "2026-07-28"
