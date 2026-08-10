"""Mock-parity proof — product surfaces via Chirp filesystem routing.

Covers the Brand chrome, Resolve schema/API/console, Star detail, Gaze,
Constellation, and Namespace pages ported from ``design/`` into ``pages/``.
"""

from __future__ import annotations

import hashlib
import json

import pytest
from chirp.testing import TestClient
from test_app import _modern_mcp_headers, _modern_mcp_params

from catalog import CATALOG, Catalog, ResolveRecord


@pytest.mark.issue(18)
class TestResolveSchema:
    """Resolve record schema + lookup (Skill DNS)."""

    def test_seed_catalog_has_expected_records(self, example_app) -> None:
        names = {r.name for r in CATALOG.all()}
        assert {
            "orrery/html-to-pdf",
            "orrery/world-time",
            "acme/release-gate",
            "acme/launch-gate",
        } <= names

    def test_resolve_by_full_name(self, example_app) -> None:
        rec = CATALOG.resolve("orrery/html-to-pdf")
        assert rec is not None
        assert rec.endpoint == "mcp://orrery.lol/stars/html-to-pdf/mcp"
        assert rec.kind == "star"

    def test_resolve_by_bare_and_versioned_name(self, example_app) -> None:
        assert CATALOG.resolve("html-to-pdf").name == "orrery/html-to-pdf"
        assert CATALOG.resolve("orrery/html-to-pdf@1.2.0").name == "orrery/html-to-pdf"

    def test_resolve_miss_returns_none(self, example_app) -> None:
        assert CATALOG.resolve("does-not-exist") is None
        assert CATALOG.resolve("") is None

    def test_record_serialization_contract(self, example_app) -> None:
        payload = CATALOG.get("orrery/html-to-pdf").as_dict()
        assert set(payload) >= {
            "name",
            "endpoint",
            "content_digest",
            "key_id",
            "price_per_call",
            "alg",
        }
        assert payload["content_digest"].startswith("sha256:")

    def test_href_routes_by_kind(self) -> None:
        star = ResolveRecord(name="a/b", endpoint="mcp://x", content_digest="sha256:0")
        gate = ResolveRecord(
            name="a/c", endpoint="mcp://x", content_digest="sha256:0", kind="constellation"
        )
        assert star.href == "/star/a/b"
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
            assert body["endpoint"] == "mcp://orrery.lol/stars/html-to-pdf/mcp"

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
                # Ops console is footer-only — not primary product nav.
                assert ">Ops · console<" in r.text, path
                assert 'aria-label="Primary"' in r.text, path
                nav_start = r.text.index('aria-label="Primary"')
                nav_end = r.text.index("</nav>", nav_start)
                primary = r.text[nav_start:nav_end]
                assert "/console" not in primary, path
                assert ">Console<" not in primary, path

    async def test_active_nav_marked_per_page(self, example_app) -> None:
        async with TestClient(example_app) as client:
            gaze = await client.get("/gaze")
            assert 'href="/gaze" aria-current="page"' in gaze.text
            resolve = await client.get("/resolve")
            assert 'href="/resolve" aria-current="page"' in resolve.text
            console = await client.get("/console")
            assert "Skill console" in console.text
            assert "/console/html-to-pdf" in console.text


@pytest.mark.issue(21)
class TestResolveConsole:
    async def test_zone_table_lists_catalog_records(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/resolve")
            assert r.status == 200
            assert "data-resolve-table" in r.text
            assert "orrery/html-to-pdf" in r.text
            assert "/console/html-to-pdf" in r.text
            assert "orrery/world-time" in r.text

    async def test_lookup_highlights_resolved_row(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/resolve?q=world-time")
            assert "row-resolved" in r.text
            assert "Resolved · world-time" in r.text


@pytest.mark.issue(25)
@pytest.mark.issue(26)
@pytest.mark.issue(27)
class TestStarDetail:
    async def test_catalog_is_a_browseable_public_sky(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/stars")
            assert r.status == 200
            assert "Find something your agent can point at" in r.text
            assert "data-star-search" in r.text
            assert "orrery/html-to-pdf" in r.text
            assert "Document processing" in r.text
            assert 'href="/star/orrery/html-to-pdf"' in r.text

    async def test_catalog_exposes_accessible_native_facet_controls(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/stars")

            assert r.status == 200
            assert "<fieldset" in r.text
            assert "<legend" in r.text
            assert "data-star-facets" in r.text
            assert 'type="checkbox"' in r.text
            assert "data-star-facet" in r.text
            assert "data-result-count" in r.text

    async def test_canonical_star_page_has_docs_relationships_and_actions(
        self, example_app
    ) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/star/orrery/world-time")
            assert r.status == 200
            assert "<!DOCTYPE html>" in r.text
            assert "/static/styles.css" in r.text
            assert 'class="topbar"' in r.text
            assert "orrery/world-time" in r.text
            assert "How it works" in r.text
            assert "In constellations" in r.text
            assert "Copy MCP URL" in r.text
            assert "Trust signal" in r.text

    async def test_legacy_star_url_remains_usable_and_unknown_is_404(self, example_app) -> None:
        async with TestClient(example_app) as client:
            old = await client.get("/stars?name=orrery/world-time")
            assert old.status == 200
            assert "orrery/world-time" in old.text
            r = await client.get("/stars?name=does-not-exist")
            assert r.status == 404

    async def test_constellation_name_is_not_a_star_page(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/stars?name=acme/launch-gate")
            assert r.status == 404



@pytest.mark.issue(37)
class TestReactiveWorldTimeStar:
    def test_signed_world_time_receipt_verifies(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(
            "ORRERY_WORLD_TIME_JSON",
            json.dumps(
                {
                    "dateTime": "2026-08-08T12:00:00",
                    "date": "08/08/2026",
                    "time": "12:00",
                    "timeZone": "UTC",
                    "dayOfWeek": "Saturday",
                }
            ),
        )
        from dogfood import signed_world_time_receipt, verify_receipt

        receipt, verified = signed_world_time_receipt()
        assert verified is True
        assert receipt["skill"] == "world-time"
        assert receipt["tool"] == "answer"
        assert receipt["key_id"] == "orrery-world-time-1"
        assert receipt["payload"]["live_at_call"] is True
        assert receipt["payload"]["datetime"] == "2026-08-08T12:00:00"
        assert "clone_warning" in receipt["payload"]
        assert verify_receipt(receipt) is True

    def test_gaze_match_world_time_has_price_no_payload(self, example_app) -> None:
        hits = CATALOG.match("live utc clock now", node="public")
        names = [h.name for h in hits]
        assert "orrery/world-time" in names
        assert names[0] == "orrery/world-time"
        hit = next(h for h in hits if h.name == "orrery/world-time")
        wire = hit.as_dict()
        assert hit.price is None
        assert "Free" in hit.blurb
        assert "Live UTC" in hit.blurb or "call time" in hit.blurb.lower()
        assert "payload" not in wire
        assert "datetime" not in wire
        assert "clone_warning" not in wire

    def test_resolve_world_time_returns_price(self, example_app) -> None:
        rec = CATALOG.resolve("orrery/world-time")
        assert rec is not None
        assert rec.price_per_call is None
        assert rec.tools == ("fetch", "get", "answer")
        assert "payload" not in rec.as_dict()

    async def test_api_resolve_world_time_price(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/api/resolve?name=orrery/world-time")
            assert r.status == 200
            body = json.loads(r.text)
            assert body["name"] == "orrery/world-time"
            assert body["price_per_call"] is None
            assert body["endpoint"] == "mcp://orrery.lol/stars/world-time/mcp"
            assert "payload" not in body

    async def test_mcp_answer_returns_signed_envelope(self, example_app) -> None:
        async with TestClient(example_app) as client:
            called = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "id": 37,
                    "params": {
                        "_meta": {
                            "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                            "io.modelcontextprotocol/clientCapabilities": {},
                        },
                        "name": "answer",
                        "arguments": {},
                    },
                },
                headers={
                    "content-type": "application/json",
                    "mcp-protocol-version": "2026-07-28",
                    "mcp-method": "tools/call",
                    "mcp-name": "answer",
                },
            )
            assert called.status == 200
            text = json.loads(called.text)["result"]["content"][0]["text"]
            assert "world-time" in text
            assert "live_at_call" in text
            assert "2026-08-08T12:00:00" in text
            assert "signature" in text
            assert "input_digest" in text or "sha256:" in text

    async def test_mcp_gaze_describe_world_time_no_payload(self, example_app) -> None:
        async with TestClient(example_app) as client:
            described = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "id": 38,
                    "params": {
                        "_meta": {
                            "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                            "io.modelcontextprotocol/clientCapabilities": {},
                        },
                        "name": "gaze_describe",
                        "arguments": {"name": "orrery/world-time"},
                    },
                },
                headers={
                    "content-type": "application/json",
                    "mcp-protocol-version": "2026-07-28",
                    "mcp-method": "tools/call",
                    "mcp-name": "gaze_describe",
                },
            )
            assert described.status == 200
            text = json.loads(described.text)["result"]["content"][0]["text"]
            assert "price_per_call': None" in text or "'price_per_call': null" in text
            assert "fetch" in text
            assert "live_at_call" not in text
            assert "clone_warning" not in text


@pytest.mark.issue(26)
@pytest.mark.issue(27)
@pytest.mark.issue(35)
class TestEnvelopeVerifyAndPdfArtifact:
    def test_signed_convert_receipt_verifies(self) -> None:
        from dogfood import signed_convert_receipt, verify_receipt

        receipt, verified = signed_convert_receipt()
        assert verified is True
        assert receipt["tool"] == "convert"
        assert receipt["key_id"] == "orrery-pdf-1"
        assert receipt["payload"]["content_type"] == "application/pdf"
        assert receipt["payment_id"]
        assert receipt["price_per_call"] is None
        assert verify_receipt(receipt) is True

    def test_tampered_receipt_fails_closed(self) -> None:
        from dogfood import signed_convert_receipt, verify_receipt

        receipt, _ = signed_convert_receipt()
        forged = dict(receipt)
        forged["payload"] = {
            "page_count": 999,
            "byte_length": 1,
            "content_type": "application/pdf",
        }
        assert verify_receipt(forged) is False

    async def test_pdf_artifact_download_matches_signed_checksum(self, example_app) -> None:
        from dogfood import signed_convert_receipt

        receipt, verified = signed_convert_receipt("<h1>Release evidence</h1><p>Ready.</p>")
        assert verified is True
        payload = receipt["payload"]

        async with TestClient(example_app) as client:
            downloaded = await client.get(str(payload["artifact_url"]))
            missing = await client.get("/artifacts/not-a-real-artifact")

        assert downloaded.status == 200
        assert downloaded.body_bytes.startswith(b"%PDF-")
        assert downloaded.header("Content-Disposition") is not None
        assert downloaded.header("Cache-Control") == "no-store"
        assert payload["sha256"] == f"sha256:{hashlib.sha256(downloaded.body_bytes).hexdigest()}"
        assert missing.status == 404

    async def test_api_verify_ok_and_forge_fail(self, example_app, caplog) -> None:
        import logging

        from dogfood import signed_convert_receipt

        receipt, _ = signed_convert_receipt()
        async with TestClient(example_app) as client:
            with caplog.at_level(logging.WARNING, logger="orrery.commerce"):
                ok = await client.post("/api/envelope/verify", json=receipt)
            assert ok.status == 200
            ok_body = json.loads(ok.text)
            assert ok_body["verified"] is True
            assert ok_body["payment_id"] == receipt["payment_id"]
            assert ok_body["price_per_call"] is None
            assert ok_body["commerce"]["action"] == "charge"
            assert ok_body["commerce"]["stub"] is True
            assert "commerce.charge_stub" in caplog.text

            forged = dict(receipt)
            forged["nonce"] = "tampered-nonce"
            with caplog.at_level(logging.WARNING, logger="orrery.commerce"):
                bad = await client.post("/api/envelope/verify", json=forged)
            assert bad.status == 200
            bad_body = json.loads(bad.text)
            assert bad_body["verified"] is False
            assert bad_body["commerce"]["action"] == "refund"
            assert bad_body["commerce"]["stub"] is True
            assert "commerce.refund_stub" in caplog.text

    async def test_mcp_convert_returns_signed_envelope(self, example_app) -> None:
        async with TestClient(example_app) as client:
            called = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "id": 27,
                    "params": {
                        "_meta": {
                            "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                            "io.modelcontextprotocol/clientCapabilities": {},
                        },
                        "name": "convert",
                        "arguments": {"html": "<html><body>hi</body></html>"},
                    },
                },
                headers={
                    "content-type": "application/json",
                    "mcp-protocol-version": "2026-07-28",
                    "mcp-method": "tools/call",
                    "mcp-name": "convert",
                },
            )
            assert called.status == 200
            text = json.loads(called.text)["result"]["content"][0]["text"]
            assert "application/pdf" in text
            assert "html-to-pdf" in text
            assert "input_digest" in text or "sha256:" in text
            assert "signature" in text


@pytest.mark.issue(35)
class TestCommerceStubs:
    def test_stubs_are_loud_not_silent(self, caplog) -> None:
        import logging

        from commerce import charge_on_verify, refund_on_forge

        with caplog.at_level(logging.WARNING, logger="orrery.commerce"):
            charged = charge_on_verify(
                payment_id="pay_test",
                price_per_call="$0.02",
                skill="html-to-pdf",
                nonce="n1",
            )
            refunded = refund_on_forge(
                payment_id="pay_test",
                price_per_call="$0.02",
                skill="html-to-pdf",
                nonce="n1",
            )
        assert charged["status"] == "stub_charged"
        assert refunded["status"] == "stub_refunded"
        assert "commerce.charge_stub" in caplog.text
        assert "commerce.refund_stub" in caplog.text

    async def test_star_catalog_is_read_only(self, example_app, caplog) -> None:
        import logging

        async with TestClient(example_app) as client:
            with caplog.at_level(logging.WARNING, logger="orrery.commerce"):
                r = await client.get("/stars")
            assert r.status == 200
            assert "Public sky" in r.text
            assert "commerce.charge_stub" not in caplog.text

    async def test_resolve_and_gaze_include_price(self, example_app) -> None:
        async with TestClient(example_app) as client:
            resolve = await client.get("/api/resolve?name=html-to-pdf")
            assert resolve.status == 200
            assert json.loads(resolve.text)["price_per_call"] is None

            gaze = await client.get("/api/gaze/match?intent=html+pdf")
            assert gaze.status == 200
            hits = json.loads(gaze.text)["hits"]
            pdf_hits = [h for h in hits if h["name"] == "orrery/html-to-pdf"]
            assert pdf_hits
            assert pdf_hits[0]["price"] is None
            assert "Free" in pdf_hits[0]["blurb"]


@pytest.mark.issue(19)
@pytest.mark.issue(20)
class TestResolveHttpAndMcp:
    async def test_resolve_name_query_returns_json(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/resolve?name=html-to-pdf")
            assert r.status == 200
            body = json.loads(r.text)
            assert body["name"] == "orrery/html-to-pdf"
            assert body["endpoint"] == "mcp://orrery.lol/stars/html-to-pdf/mcp"
            assert body["key_id"] == "orrery-pdf-1"

    async def test_resolve_html_console_still_renders(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/resolve")
            assert r.status == 200
            assert "data-resolve-table" in r.text
            assert "orrery/html-to-pdf" in r.text
            assert "orrery/world-time" in r.text

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
            assert "mcp://orrery.lol/stars/html-to-pdf/mcp" in text
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


@pytest.mark.issue(22)
class TestGazeCatalog:
    def test_match_ranks_html_pdf_intent(self, example_app) -> None:
        hits = CATALOG.match("html pdf convert", node="public")
        names = [h.name for h in hits]
        assert "orrery/html-to-pdf" in names
        assert names[0] == "orrery/html-to-pdf"
        hit = hits[0]
        assert hit.kind == "star"
        assert hit.endpoint
        assert "payload" not in hit.as_dict()
        assert "tools" not in hit.as_dict()

    def test_match_namespace_node_scopes_acme(self, example_app) -> None:
        hits = CATALOG.match("ship gate", node="acme")
        assert hits
        assert all(h.name.startswith("acme/") for h in hits)

    def test_search_and_describe_and_list_constellations(self, example_app) -> None:
        searched = CATALOG.search("world-time")
        assert any(h.name == "orrery/world-time" for h in searched)

        described = CATALOG.describe("orrery/html-to-pdf")
        assert described["status"] == "ok"
        assert described["tools"] == ["convert", "submit", "result", "health"]
        assert described["price_per_call"] is None
        assert described["content_digest"].startswith("sha256:")

        consts = CATALOG.list_constellations()
        assert {h.name for h in consts} >= {
            "acme/release-gate",
            "acme/launch-gate",
            "orrery/stale-proof",
        }
        assert all(h.kind == "constellation" for h in consts)

        launch = CATALOG.describe("acme/launch-gate")
        assert launch["kind"] == "constellation"
        assert launch["policy_nodes"] == [
            "secret-scan",
            "license",
            "html-to-pdf",
            "human-approve",
            "release",
        ]
        assert any(e["kind"] == "repair_loop" for e in launch["policy_edges"])

    def test_describe_miss(self, example_app) -> None:
        assert CATALOG.describe("nope")["error"] == "not_found"


@pytest.mark.issue(23)
class TestGazeMcpTools:
    async def test_tools_list_exposes_gaze_set(self, example_app) -> None:
        async with TestClient(example_app) as client:
            listed = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/list",
                    "id": 20,
                    "params": {
                        "_meta": {
                            "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                            "io.modelcontextprotocol/clientCapabilities": {},
                        },
                    },
                },
                headers={
                    "content-type": "application/json",
                    "mcp-protocol-version": "2026-07-28",
                    "mcp-method": "tools/list",
                },
            )
            assert listed.status == 200
            names = {t["name"] for t in json.loads(listed.text)["result"]["tools"]}
            assert {
                "gaze_match",
                "gaze_search",
                "gaze_describe",
                "gaze_list_constellations",
            } <= names

    async def test_mcp_search_describe_list(self, example_app) -> None:
        async with TestClient(example_app) as client:
            searched = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "id": 21,
                    "params": {
                        "_meta": {
                            "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                            "io.modelcontextprotocol/clientCapabilities": {},
                        },
                        "name": "gaze_search",
                        "arguments": {"query": "html-to-pdf"},
                    },
                },
                headers={
                    "content-type": "application/json",
                    "mcp-protocol-version": "2026-07-28",
                    "mcp-method": "tools/call",
                    "mcp-name": "gaze_search",
                },
            )
            assert searched.status == 200
            assert "orrery/html-to-pdf" in json.loads(searched.text)["result"]["content"][0]["text"]

            described = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "id": 22,
                    "params": {
                        "_meta": {
                            "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                            "io.modelcontextprotocol/clientCapabilities": {},
                        },
                        "name": "gaze_describe",
                        "arguments": {"name": "orrery/html-to-pdf"},
                    },
                },
                headers={
                    "content-type": "application/json",
                    "mcp-protocol-version": "2026-07-28",
                    "mcp-method": "tools/call",
                    "mcp-name": "gaze_describe",
                },
            )
            text = json.loads(described.text)["result"]["content"][0]["text"]
            assert "convert" in text
            assert "sha256:" in text

            listed = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "id": 23,
                    "params": {
                        "_meta": {
                            "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                            "io.modelcontextprotocol/clientCapabilities": {},
                        },
                        "name": "gaze_list_constellations",
                        "arguments": {},
                    },
                },
                headers={
                    "content-type": "application/json",
                    "mcp-protocol-version": "2026-07-28",
                    "mcp-method": "tools/call",
                    "mcp-name": "gaze_list_constellations",
                },
            )
            text = json.loads(listed.text)["result"]["content"][0]["text"]
            assert "acme/launch-gate" in text


@pytest.mark.issue(24)
class TestGazeConsole:
    async def test_gaze_renders_catalog_names(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/gaze")
            assert r.status == 200
            assert "gaze-nodes" in r.text
            assert "mcp://orrery.lol/gaze" in r.text
            assert "orrery/html-to-pdf" in r.text
            assert "orrery/world-time" in r.text
            assert "acme/launch-gate" in r.text
            assert "look_at" not in r.text
            assert "gaze_match" in r.text

    async def test_gaze_intent_query_filters_hits(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/gaze?intent=html+pdf&node=public")
            assert r.status == 200
            assert "orrery/html-to-pdf" in r.text

    async def test_gaze_alpine_config_avoids_x_data_breakout(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get(
                "/gaze?intent=say+%22hi%22+%3Cscript%3Ealert(1)%3C/script%3E&node=public"
            )
            assert r.status == 200
            assert 'id="gaze-cfg"' in r.text
            assert "getElementById('gaze-cfg')" in r.text

            # Server config is a JSON script body (Chirp alpine_json_config).
            start = r.text.index('id="gaze-cfg"')
            open_tag = r.text.index(">", start) + 1
            close_tag = r.text.index("</script>", open_tag)
            cfg = json.loads(r.text[open_tag:close_tag])
            assert cfg["node"] == "public"
            assert cfg["q"] == 'say "hi" <script>alert(1)</script>'

            # x-data attribute stays intact (old Markup(json.dumps) closed it early).
            attr_start = r.text.index('x-data="') + len('x-data="')
            attr_end = r.text.index('"', attr_start)
            attr = r.text[attr_start:attr_end]
            assert "runMatch" in attr
            assert "scrollIntoView" in attr
            assert "renderHit" in attr
            assert "kindPill" in attr

    async def test_api_gaze_match(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/api/gaze/match?intent=live+utc&node=public")
            assert r.status == 200
            body = json.loads(r.text)
            assert body["status"] == "ok"
            names = [h["name"] for h in body["hits"]]
            assert "orrery/world-time" in names


@pytest.mark.issue(32)
class TestConstellation:
    async def test_graph_and_composite_receipt(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/constellations")
            assert r.status == 200
            assert "data-constellation" in r.text
            assert "<svg" in r.text
            assert "acme/launch-gate" in r.text
            assert "secret-scan" in r.text
            assert "html-to-pdf*" in r.text
            assert "Composite receipt" in r.text
            assert "Reliability console" in r.text


@pytest.mark.issue(31)
class TestConstellationPolicyModel:
    def test_launch_gate_policy_fixture(self, example_app) -> None:
        from catalog.constellation import LAUNCH_GATE_POLICY, policy_for

        graph = policy_for("acme/launch-gate")
        assert graph is LAUNCH_GATE_POLICY
        assert len(graph.nodes) == 5
        assert any(n.star_ref == "orrery/html-to-pdf" for n in graph.nodes)
        assert graph.repair_loop_max == 3
        assert any(e.kind == "repair_loop" for e in graph.edges)
        assert len(graph.composite_chain) == 4

    def test_stale_proof_policy_fixture(self, example_app) -> None:
        from catalog.constellation import STALE_PROOF_POLICY, policy_for

        graph = policy_for("orrery/stale-proof")
        assert graph is STALE_PROOF_POLICY
        assert len(graph.nodes) == 3
        refs = {n.star_ref for n in graph.nodes if n.star_ref}
        assert refs == {
            "orrery/world-time",
            "orrery/source-watch",
        }
        assert graph.repair_loop_max is None
        assert len(graph.composite_chain) == 2
        assert "separate managed Star" in graph.footnote


@pytest.mark.issue(33)
class TestConstellationMCP:
    async def test_tools_list_exposes_constellation_tools(self, example_app) -> None:
        async with TestClient(example_app) as client:
            listed = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/list",
                    "id": 1,
                    "params": _modern_mcp_params(),
                },
                headers=_modern_mcp_headers("tools/list"),
            )
            tool_names = {t["name"] for t in json.loads(listed.text)["result"]["tools"]}
            assert {"run", "status", "explain_policy"} <= tool_names

    async def test_run_returns_chained_step_receipts(self, example_app) -> None:
        async with TestClient(example_app) as client:
            called = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "id": 2,
                    "params": _modern_mcp_params(
                        name="run",
                        arguments={
                            "pages": ["README.md"],
                            "links": [],
                            "examples": [],
                        },
                    ),
                },
                headers=_modern_mcp_headers("tools/call", "run"),
            )
            assert called.status == 200
            body = json.loads(called.text)["result"]["content"][0]["text"]
            assert "secret-scan" in body
            assert "license" in body
            assert "html-to-pdf" in body
            assert "human-approve" in body
            assert "run_id" in body
            assert "Envelope" in body or "signature" in body

    async def test_status_returns_latest_chain(self, example_app) -> None:
        async with TestClient(example_app) as client:
            await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "id": 3,
                    "params": _modern_mcp_params(
                        name="run",
                        arguments={"pages": ["guide.md"]},
                    ),
                },
                headers=_modern_mcp_headers("tools/call", "run"),
            )
            status = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "id": 4,
                    "params": _modern_mcp_params(name="status", arguments={}),
                },
                headers=_modern_mcp_headers("tools/call", "status"),
            )
            text = json.loads(status.text)["result"]["content"][0]["text"]
            assert "completed" in text
            assert "secret-scan" in text

    async def test_explain_policy_describes_gates_and_loops(self, example_app) -> None:
        async with TestClient(example_app) as client:
            called = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "id": 5,
                    "params": _modern_mcp_params(
                        name="explain_policy",
                        arguments={"name": "acme/launch-gate"},
                    ),
                },
                headers=_modern_mcp_headers("tools/call", "explain_policy"),
            )
            text = json.loads(called.text)["result"]["content"][0]["text"]
            assert "secret-scan" in text
            assert "repair" in text.lower()
            assert "fan" in text.lower()

    async def test_stale_proof_run_and_explain(self, example_app) -> None:
        async with TestClient(example_app) as client:
            called = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "id": 6,
                    "params": _modern_mcp_params(
                        name="run",
                        arguments={
                            "pages": ["README.md"],
                            "constellation": "orrery/stale-proof",
                        },
                    ),
                },
                headers=_modern_mcp_headers("tools/call", "run"),
            )
            assert called.status == 200
            body = json.loads(called.text)["result"]["content"][0]["text"]
            assert "orrery/stale-proof" in body
            assert "world-time" in body
            assert "source-watch" in body
            assert "html-to-pdf" not in body
            assert "run_id" in body

            explained = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "id": 7,
                    "params": _modern_mcp_params(
                        name="explain_policy",
                        arguments={"name": "orrery/stale-proof"},
                    ),
                },
                headers=_modern_mcp_headers("tools/call", "explain_policy"),
            )
            text = json.loads(explained.text)["result"]["content"][0]["text"]
            assert "Parable" in text or "parable" in text.lower()
            assert "clone" in text.lower()
            assert "separate managed Star" in text


@pytest.mark.issue(88)
class TestStaleProofConstellation:
    def test_resolve_and_gaze_blurb(self, example_app) -> None:
        from catalog import CATALOG

        rec = CATALOG.resolve("orrery/stale-proof")
        assert rec is not None
        assert rec.kind == "constellation"
        assert rec.visibility == "public"
        assert "clone" in (rec.description or "").lower()
        described = CATALOG.describe("orrery/stale-proof")
        assert described["kind"] == "constellation"
        blurbs = CATALOG.match("stale proof clone", node="public")
        assert any(h.name == "orrery/stale-proof" for h in blurbs)
        hit = next(h for h in blurbs if h.name == "orrery/stale-proof")
        assert "clone" in hit.blurb.lower() or "live" in hit.blurb.lower()

    async def test_constellation_page_explains_parable(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/constellations?name=orrery/stale-proof")
            assert r.status == 200
            assert "orrery/stale-proof" in r.text
            assert "world-time" in r.text
            assert "source-watch" in r.text
            assert "Why cloning fails" in r.text
            assert "Teaching trio" in r.text


@pytest.mark.issue(29)
class TestNamespaces:
    async def test_namespace_pitch_renders(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/namespaces")
            assert r.status == 200
            assert "acme/*" in r.text
            assert "Private by default" in r.text
