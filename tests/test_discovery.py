"""Public agent discovery endpoints (llms.txt, MCP well-known, /connect)."""

from __future__ import annotations

import json

import pytest
from chirp.testing import TestClient

from discovery import (
    MCP_TOOLS,
    TEACHING_TRIO,
    configured_public_origin,
    mcp_endpoint,
    resolve_public_origin,
)

HOST = {"Host": "orrery.lol"}


def _header(response, name: str) -> str | None:
    needle = name.lower()
    for header, value in response.headers:
        if header.lower() == needle:
            return value
    return None


def test_resolve_public_origin_prefers_config() -> None:
    assert resolve_public_origin("https://orrery.lol/", "http://127.0.0.1:8000/") == (
        "https://orrery.lol"
    )


def test_resolve_public_origin_falls_back_to_request() -> None:
    assert resolve_public_origin(None, "http://127.0.0.1:8000/llms.txt") == (
        "http://127.0.0.1:8000"
    )


def test_configured_public_origin_prefers_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORRERY_PUBLIC_ORIGIN", "https://orrery.lol/")
    monkeypatch.setenv("RAILWAY_PUBLIC_DOMAIN", "ignored.example")
    assert configured_public_origin() == "https://orrery.lol"


def test_configured_public_origin_railway_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ORRERY_PUBLIC_ORIGIN", raising=False)
    monkeypatch.setenv("RAILWAY_PUBLIC_DOMAIN", "orrery.lol")
    assert configured_public_origin() == "https://orrery.lol"


@pytest.fixture
def discovery_app(example_app, monkeypatch: pytest.MonkeyPatch):
    # Origin is resolved per-request from env (not at import time).
    monkeypatch.setenv("ORRERY_PUBLIC_ORIGIN", "https://orrery.lol")
    return example_app


@pytest.mark.asyncio
async def test_llms_txt_is_public(discovery_app) -> None:
    async with TestClient(discovery_app) as client:
        response = await client.get("/llms.txt", headers=HOST)
        assert response.status == 200
        assert "text/plain" in (response.content_type or "")
        assert "https://orrery.lol/mcp" in response.text
        assert "/connect" in response.text
        assert "/skills" in response.text
        assert "Teaching trio" in response.text
        for star in TEACHING_TRIO:
            assert star["star"] in response.text
            assert star["job"].split("—")[0].strip() in response.text or star["job"] in response.text
        assert "Do not install or clone for live truth" in response.text
        assert "orrery/stale-proof" in response.text


@pytest.mark.asyncio
async def test_llms_full_lists_tools(discovery_app) -> None:
    async with TestClient(discovery_app) as client:
        response = await client.get("/llms-full.txt", headers=HOST)
        assert response.status == 200
        for tool in MCP_TOOLS:
            assert tool["name"] in response.text
        assert "tools/list" in response.text
        assert "/stars/html-to-pdf/mcp" in response.text
        assert "gaze_match" in response.text
        assert "Install or clone for live truth" in response.text


@pytest.mark.asyncio
async def test_mcp_server_card(discovery_app) -> None:
    async with TestClient(discovery_app) as client:
        response = await client.get("/.well-known/mcp/server-card.json", headers=HOST)
        assert response.status == 200
        assert _header(response, "access-control-allow-origin") == "*"
        assert "application/json" in (response.content_type or "")
        card = json.loads(response.text)
        assert card["serverInfo"]["name"] == "orrery"
        assert card["transport"]["endpoint"] == "https://orrery.lol/mcp"
        assert card["authentication"]["required"] is False
        names = {t["name"] for t in card["tools"]}
        assert names == {t["name"] for t in MCP_TOOLS}


@pytest.mark.asyncio
async def test_mcp_manifest_and_alias(discovery_app) -> None:
    async with TestClient(discovery_app) as client:
        primary = await client.get("/.well-known/mcp", headers=HOST)
        alias = await client.get("/.well-known/mcp.json", headers=HOST)
        assert primary.status == 200
        assert alias.status == 200
        body = json.loads(primary.text)
        assert body["endpoints"]["streamable_http"] == mcp_endpoint("https://orrery.lol")
        assert body["authentication"]["required"] is False
        assert json.loads(alias.text) == body


@pytest.mark.asyncio
async def test_robots_and_security_txt(discovery_app) -> None:
    async with TestClient(discovery_app) as client:
        robots = await client.get("/robots.txt", headers=HOST)
        assert robots.status == 200
        assert "Allow: /llms.txt" in robots.text
        assert "Allow: /mcp" in robots.text
        assert "Disallow: /console" in robots.text

        security = await client.get("/.well-known/security.txt", headers=HOST)
        assert security.status == 200
        assert "Contact:" in security.text
        assert "github.com/lbliii/orrery" in security.text


@pytest.mark.asyncio
async def test_connect_page_is_public(discovery_app) -> None:
    async with TestClient(discovery_app) as client:
        page = await client.get("/connect", headers=HOST)
        assert page.status == 200
        assert "https://orrery.lol/mcp" in page.text
        assert "gaze_match" in page.text
        assert 'href="/llms.txt"' in page.text
        assert 'href="/skills"' in page.text
        assert "Teaching trio" in page.text
        assert "Do not install or clone for live truth" in page.text
        for star in TEACHING_TRIO:
            assert star["star"] in page.text
            assert star["href"] in page.text
        assert "orrery/stale-proof" in page.text


@pytest.mark.asyncio
async def test_footer_links_to_connect(discovery_app) -> None:
    async with TestClient(discovery_app) as client:
        page = await client.get("/", headers=HOST)
        assert page.status == 200
        assert 'href="/connect"' in page.text
        assert 'href="/llms.txt"' in page.text
