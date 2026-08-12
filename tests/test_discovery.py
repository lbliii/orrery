"""Public agent discovery endpoints (llms.txt, MCP well-known, /connect)."""

from __future__ import annotations

import base64
import json

import pytest
from chirp.testing import TestClient
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from discovery import (
    MCP_TOOLS,
    MCP_TOOLS_ALLOWLIST,
    MCP_TOOLS_DENYLIST,
    PUBLIC_MARKETING_ROUTES,
    SITEMAP_PATHS,
    SLIM_MCP_COPY,
    TEACHING_TRIO,
    configured_public_origin,
    llms_txt,
    mcp_endpoint,
    resolve_public_origin,
    robots_txt,
    sitemap_xml,
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


@pytest.mark.issue(302)
def test_mcp_tools_allowlist_matches_frozen_set() -> None:
    names = {t["name"] for t in MCP_TOOLS}
    assert names == MCP_TOOLS_ALLOWLIST
    assert names.isdisjoint(MCP_TOOLS_DENYLIST)
    for denied in ("convert", "fetch", "run", "answer"):
        assert denied in MCP_TOOLS_DENYLIST
        assert denied not in names


@pytest.mark.issue(302)
@pytest.mark.asyncio
async def test_discovery_copy_mentions_resolve_then_call(discovery_app) -> None:
    async with TestClient(discovery_app) as client:
        llms = await client.get("/llms.txt", headers=HOST)
        card = await client.get("/.well-known/mcp/server-card.json", headers=HOST)
        connect = await client.get("/connect", headers=HOST)
        assert llms.status == card.status == connect.status == 200
        for body in (llms.text, card.text, connect.text):
            assert "gaze/resolve" in body.lower() or "Gaze" in body
            assert "publisher" in body.lower() or "call" in body.lower()
        assert SLIM_MCP_COPY in llms.text
        assert SLIM_MCP_COPY in json.loads(card.text)["description"]
        assert SLIM_MCP_COPY in connect.text


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
        assert SLIM_MCP_COPY in response.text
        assert "orrery/stale-proof" in response.text


@pytest.mark.asyncio
async def test_llms_full_lists_tools(discovery_app) -> None:
    async with TestClient(discovery_app) as client:
        response = await client.get("/llms-full.txt", headers=HOST)
        assert response.status == 200
        for tool in MCP_TOOLS:
            assert tool["name"] in response.text
        assert "- `convert`:" not in response.text
        assert "tools/list" in response.text
        assert "/stars/html-to-pdf/mcp" in response.text
        assert "gaze_match" in response.text
        assert "Install or clone for live truth" in response.text


@pytest.mark.asyncio
async def test_llms_full_indexes_public_catalog_from_agent_cards(discovery_app) -> None:
    """Teaching trio stays first; each public Agent Card is indexed (#225)."""
    from discovery import (
        CAPABILITY_FAMILY_DESCRIPTIONS,
        PUBLIC_CATALOG_RECIPES,
        llms_full_txt,
        public_star_catalog,
        resolve_href,
    )
    from stars._core.definition import CAPABILITY_FAMILY_LABELS

    origin = "https://orrery.lol"
    async with TestClient(discovery_app) as client:
        response = await client.get("/llms-full.txt", headers=HOST)
        assert response.status == 200
        body = response.text

    # Served body matches generation from live catalog (drift guard).
    generated = llms_full_txt(origin)
    assert body.strip() == generated.strip()
    assert body.endswith("\n")
    teaching_pos = body.index("## Teaching trio")
    catalog_pos = body.index("## Public catalog")
    recipes_pos = body.index("## Recipes")
    tools_pos = body.index("## MCP tools")
    assert teaching_pos < catalog_pos < recipes_pos < tools_pos

    entries = public_star_catalog()
    assert len(entries) >= 19
    for entry in entries:
        name = str(entry["name"])
        assert f"#### `{name}`" in body
        assert str(entry["summary"]) in body
        for bullet in entry["use_when"]:
            assert bullet in body
        for intent in entry["example_intents"]:
            assert intent in body
        assert resolve_href(origin, name) in body
        family = str(entry["primary_family"])
        label = CAPABILITY_FAMILY_LABELS[family]
        assert f"### {label}" in body
        assert CAPABILITY_FAMILY_DESCRIPTIONS[family] in body

    for intent, sku in PUBLIC_CATALOG_RECIPES:
        assert intent in body
        assert f"`{sku}`" in body
        assert sku in {str(item["name"]) for item in entries}

    # content graph SKUs (#213/#215/#216) are public in llms-full.
    assert "`orrery/content-readiness`" in body
    assert "`orrery/authorized-content-patch`" in body
    assert "`orrery/publish-gate`" in body


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
        assert card["documentation"] == "https://orrery.lol/llms.txt"
        assert card["llms_full"] == "https://orrery.lol/llms-full.txt"
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
        assert body["llms_full"] == "https://orrery.lol/llms-full.txt"


def test_public_catalog_recipes_only_reference_live_skus() -> None:
    from discovery import PUBLIC_CATALOG_RECIPES, public_star_catalog

    names = {str(item["name"]) for item in public_star_catalog()}
    for _intent, sku in PUBLIC_CATALOG_RECIPES:
        assert sku in names


def test_llms_full_generation_covers_every_public_agent_card() -> None:
    """Pure drift check without HTTP — registry cards must all render."""
    from discovery import llms_full_txt, public_star_catalog

    body = llms_full_txt("https://orrery.lol")
    for entry in public_star_catalog():
        assert f"#### `{entry['name']}`" in body
        assert entry["summary"] in body



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


@pytest.mark.issue(331)
def test_discovery_lists_public_marketing_routes() -> None:
    """robots, sitemap URL set, and llms Product section (#328 inventory)."""
    origin = "https://orrery.lol"
    robots = robots_txt(origin)
    llms = llms_txt(origin)
    sitemap = sitemap_xml(origin)
    for path in PUBLIC_MARKETING_ROUTES:
        assert f"Allow: {path}" in robots
        assert f"{origin}{path}" in llms
        assert f"<loc>{origin}{path}</loc>" in sitemap
    assert "/product" in SITEMAP_PATHS
    assert "/receipts" in SITEMAP_PATHS
    assert "/how-it-works" in SITEMAP_PATHS
    assert "/for-harnesses" in SITEMAP_PATHS
    assert "/pricing" in SITEMAP_PATHS
    assert "[Overview]" in llms
    assert "[Receipts]" in llms
    assert "[How it works]" in llms
    assert "[For harnesses]" in llms
    assert "[Pricing]" in llms


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
        assert SLIM_MCP_COPY in page.text
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


PRODUCT_NAV_HREFS = (
    "/product",
    "/how-it-works",
    "/gaze",
    "/resolve",
    "/stars",
    "/constellations",
    "/receipts",
    "/namespaces",
    "/for-harnesses",
    "/pricing",
)


@pytest.mark.issue(329)
@pytest.mark.asyncio
async def test_topbar_product_dropdown_and_connect(discovery_app) -> None:
    """Primary nav: Product dropdown (#328) + Connect CTA in topbar."""
    async with TestClient(discovery_app) as client:
        page = await client.get("/", headers=HOST)
        assert page.status == 200
        nav_start = page.text.index('aria-label="Primary"')
        nav_end = page.text.index("</nav>", nav_start)
        primary = page.text[nav_start:nav_end]
        assert 'class="nav-dropdown"' in primary
        assert "Product" in primary
        assert 'href="/connect"' in primary
        assert 'class="btn nav-cta"' in primary
        for href in PRODUCT_NAV_HREFS:
            assert f'href="{href}"' in primary, href
        assert "/console" not in primary
