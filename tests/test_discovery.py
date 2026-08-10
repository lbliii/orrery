"""Public agent discovery endpoints (llms.txt, MCP well-known, /connect)."""

from __future__ import annotations

import base64
import json

import pytest
from chirp.testing import TestClient
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from discovery import (
    MCP_TOOLS,
    TEACHING_TRIO,
    configured_public_origin,
    mcp_endpoint,
    resolve_public_origin,
)
from public_keys import public_key_set

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
            job_prefix = star["job"].split("—")[0].strip()
            assert job_prefix in response.text or star["job"] in response.text
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
        assert card["envelope_keys"] == "https://orrery.lol/.well-known/orrery/keys.json"
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
        assert body["envelope_keys"] == "https://orrery.lol/.well-known/orrery/keys.json"


@pytest.mark.asyncio
async def test_public_envelope_key_set_is_cacheable_and_matches_resolve_key(discovery_app) -> None:
    async with TestClient(discovery_app) as client:
        resolved = await client.get("/api/resolve?name=orrery/html-to-pdf", headers=HOST)
        keys = await client.get("/.well-known/orrery/keys.json", headers=HOST)
        assert resolved.status == keys.status == 200
        assert "max-age=3600" in (_header(keys, "cache-control") or "")
        record, key_set = json.loads(resolved.text), json.loads(keys.text)
        assert record["public_key_url"] == "https://orrery.lol/.well-known/orrery/keys.json"
        key = next(item for item in key_set["keys"] if item["kid"] == record["key_id"])
        assert key["kty"] == "OKP" and key["crv"] == "Ed25519"
        assert key["alg"] == "EdDSA" and key["envelope_alg"] == record["alg"]


def test_key_set_enables_standalone_canonical_envelope_verification() -> None:
    from stars.html_to_pdf.skill import build_skill

    skill = build_skill()
    envelope = next(tool for tool in skill._pending if tool.name == "convert").handler(
        html="<p>x</p>"
    )
    wire = envelope.to_wire()
    entry = next(
        item
        for item in public_key_set({"orrery/html-to-pdf": skill}, origin="https://example.test")[
            "keys"
        ]
        if item["kid"] == wire["key_id"]
    )
    fields = {
        name: wire[name]
        for name in (
            "payload",
            "skill",
            "version",
            "tool",
            "nonce",
            "input_digest",
            "key_id",
            "alg",
        )
    }
    message = json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    encoded = str(entry["x"])
    public = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    Ed25519PublicKey.from_public_bytes(public).verify(base64.b64decode(wire["signature"]), message)


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
        assert "Canonical: https://orrery.lol/.well-known/security.txt" in security.text
        assert "Policy: https://orrery.lol/security" in security.text
        assert "Expires:" in security.text
        assert "Sitemap: https://orrery.lol/sitemap.xml" in robots.text


@pytest.mark.asyncio
async def test_public_trust_center_and_machine_metadata(discovery_app) -> None:
    async with TestClient(discovery_app) as client:
        for path, expected in (
            ("/security", "arbitrary command"),
            ("/privacy", "15 minutes"),
            ("/terms", "deploy"),
            ("/contact", "Security Advisories"),
            ("/trust/allowlist", "HTTPS/TCP 443"),
        ):
            response = await client.get(path, headers=HOST)
            assert response.status == 200
            assert expected in response.text

        trust = await client.get("/.well-known/orrery/trust.json", headers=HOST)
        assert trust.status == 200
        assert "signed Ed25519 Envelopes" in trust.text
        assert "15 minutes" in trust.text

        sitemap = await client.get("/sitemap.xml", headers=HOST)
        assert sitemap.status == 200
        assert "application/xml" in (sitemap.content_type or "")
        assert "https://orrery.lol/security" in sitemap.text


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
