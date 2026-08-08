"""Mock-parity proof — product surfaces via Chirp filesystem routing.

Covers the Brand chrome, Resolve schema/API/console, Star detail, Gaze,
Constellation, and Namespace pages ported from ``design/`` into ``pages/``.
"""

from __future__ import annotations

import json

import pytest
from chirp.testing import TestClient

from catalog import CATALOG, Catalog, ResolveRecord


@pytest.mark.issue(18)
class TestResolveSchema:
    """Resolve record schema + lookup (Skill DNS)."""

    def test_seed_catalog_has_expected_records(self) -> None:
        names = {r.name for r in CATALOG.all()}
        assert {"orrery/html-to-pdf", "orrery/md-linkcheck", "acme/release-gate"} <= names

    def test_resolve_by_full_name(self) -> None:
        rec = CATALOG.resolve("orrery/html-to-pdf")
        assert rec is not None
        assert rec.endpoint == "mcp://orrery.dev/s/html-to-pdf"
        assert rec.kind == "star"

    def test_resolve_by_bare_and_versioned_name(self) -> None:
        assert CATALOG.resolve("html-to-pdf").name == "orrery/html-to-pdf"
        assert CATALOG.resolve("orrery/html-to-pdf@1.2.0").name == "orrery/html-to-pdf"

    def test_resolve_miss_returns_none(self) -> None:
        assert CATALOG.resolve("does-not-exist") is None
        assert CATALOG.resolve("") is None

    def test_record_serialization_contract(self) -> None:
        payload = CATALOG.get("orrery/html-to-pdf").as_dict()
        assert set(payload) >= {
            "name",
            "endpoint",
            "content_digest",
            "key_id",
            "price_per_call",
            "alg",
        }

    def test_href_routes_by_kind(self) -> None:
        star = ResolveRecord(name="a/b", endpoint="mcp://x", content_digest="sha256:0")
        gate = ResolveRecord(
            name="a/c", endpoint="mcp://x", content_digest="sha256:0", kind="constellation"
        )
        assert star.href.startswith("/stars?name=")
        assert gate.href.startswith("/constellations?name=")

    def test_public_zone_excludes_private_stars(self) -> None:
        cat = Catalog(
            (
                ResolveRecord(name="p/pub", endpoint="m", content_digest="d"),
                ResolveRecord(
                    name="p/priv", endpoint="m", content_digest="d", visibility="private"
                ),
            )
        )
        public = {r.name for r in cat.public_records()}
        assert "p/pub" in public
        assert "p/priv" not in public  # private star hidden from public zone


@pytest.mark.issue(19)
class TestResolveApi:
    async def test_api_resolve_returns_record_json(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/api/resolve?name=html-to-pdf")
            assert r.status == 200
            body = json.loads(r.text)
            assert body["name"] == "orrery/html-to-pdf"
            assert body["endpoint"] == "mcp://orrery.dev/s/html-to-pdf"

    async def test_api_resolve_404_on_miss(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/api/resolve?name=nope")
            assert r.status == 404
            assert json.loads(r.text)["error"] == "not_found"


@pytest.mark.issue(15)
@pytest.mark.issue(16)
class TestBrandChrome:
    async def test_static_design_assets_served(self, example_app) -> None:
        async with TestClient(example_app) as client:
            css = await client.get("/static/styles.css")
            assert css.status == 200
            assert ".cosmos" in css.text
            js = await client.get("/static/motion.js")
            assert js.status == 200
            assert "settleDigest" in js.text

    async def test_layout_topbar_and_cosmos_on_every_page(self, example_app) -> None:
        async with TestClient(example_app) as client:
            for path in ("/", "/gaze", "/resolve", "/stars", "/constellations", "/namespaces"):
                r = await client.get(path)
                assert r.status == 200, path
                assert 'class="topbar"' in r.text, path
                assert 'class="cosmos"' in r.text, path
                assert "/static/styles.css" in r.text, path
                assert "fonts.googleapis.com" in r.text, path

    async def test_active_nav_marked_per_page(self, example_app) -> None:
        async with TestClient(example_app) as client:
            gaze = await client.get("/gaze")
            assert 'href="/gaze" aria-current="page"' in gaze.text
            resolve = await client.get("/resolve")
            assert 'href="/resolve" aria-current="page"' in resolve.text


@pytest.mark.issue(21)
class TestResolveConsole:
    async def test_zone_table_lists_catalog_records(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/resolve")
            assert r.status == 200
            assert "data-resolve-table" in r.text
            assert "orrery/html-to-pdf" in r.text
            assert "orrery/md-linkcheck" in r.text

    async def test_lookup_highlights_resolved_row(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/resolve?q=md-linkcheck")
            assert "row-resolved" in r.text
            assert "Resolved · md-linkcheck" in r.text


@pytest.mark.issue(25)
@pytest.mark.issue(26)
class TestStarDetail:
    async def test_default_star_manifest_and_receipt(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/stars")
            assert r.status == 200
            assert "orrery/html-to-pdf@1.2.0" in r.text
            assert "mcp://orrery.dev/s/html-to-pdf" in r.text
            assert "Last Envelope" in r.text
            assert "data-receipt" in r.text

    async def test_named_star_switches_record(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/stars?name=orrery/md-linkcheck")
            assert r.status == 200
            assert "orrery/md-linkcheck" in r.text
            assert "$0.01" in r.text

    async def test_unknown_star_name_is_404(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/stars?name=does-not-exist")
            assert r.status == 404

    async def test_constellation_name_is_not_a_star_page(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/stars?name=acme/launch-gate")
            assert r.status == 404


@pytest.mark.issue(19)
@pytest.mark.issue(20)
class TestResolveHttpAndMcp:
    async def test_resolve_name_query_returns_json(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/resolve?name=html-to-pdf")
            assert r.status == 200
            body = json.loads(r.text)
            assert body["name"] == "orrery/html-to-pdf"
            assert body["endpoint"] == "mcp://orrery.dev/s/html-to-pdf"
            assert body["key_id"] == "orrery-pdf-1"

    async def test_resolve_html_console_still_renders(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/resolve")
            assert r.status == 200
            assert "data-resolve-table" in r.text
            assert "orrery/html-to-pdf" in r.text

    async def test_mcp_resolve_name_returns_dns_record(self, example_app) -> None:
        async with TestClient(example_app) as client:
            called = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "id": 9,
                    "params": {
                        "_meta": {
                            "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                            "io.modelcontextprotocol/clientCapabilities": {},
                        },
                        "name": "resolve_name",
                        "arguments": {"name": "orrery/html-to-pdf"},
                    },
                },
                headers={
                    "content-type": "application/json",
                    "mcp-protocol-version": "2026-07-28",
                    "mcp-method": "tools/call",
                    "mcp-name": "resolve_name",
                },
            )
            assert called.status == 200
            text = json.loads(called.text)["result"]["content"][0]["text"]
            assert "orrery/html-to-pdf" in text
            assert "mcp://orrery.dev/s/html-to-pdf" in text
            assert "/console/" not in text
            assert "sha256:" in text

    async def test_mcp_resolve_name_miss(self, example_app) -> None:
        async with TestClient(example_app) as client:
            called = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "id": 10,
                    "params": {
                        "_meta": {
                            "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                            "io.modelcontextprotocol/clientCapabilities": {},
                        },
                        "name": "resolve_name",
                        "arguments": {"name": "nope"},
                    },
                },
                headers={
                    "content-type": "application/json",
                    "mcp-protocol-version": "2026-07-28",
                    "mcp-method": "tools/call",
                    "mcp-name": "resolve_name",
                },
            )
            assert called.status == 200
            text = json.loads(called.text)["result"]["content"][0]["text"]
            assert "not_found" in text

    async def test_gaze_renders_nodes_and_alpine(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/gaze")
            assert r.status == 200
            assert "gaze-nodes" in r.text
            assert "x-data" in r.text
            assert "mcp://orrery.dev/gaze" in r.text


@pytest.mark.issue(32)
class TestConstellation:
    async def test_graph_and_composite_receipt(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/constellations")
            assert r.status == 200
            assert "data-constellation" in r.text
            assert "<svg" in r.text
            assert "acme/launch-gate" in r.text
            assert "Composite receipt" in r.text


@pytest.mark.issue(29)
class TestNamespaces:
    async def test_namespace_pitch_renders(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/namespaces")
            assert r.status == 200
            assert "acme/*" in r.text
            assert "Private by default" in r.text
