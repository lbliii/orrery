"""Mock-parity proof — product surfaces via Chirp filesystem routing.

Covers the Brand chrome, Resolve schema/API/console, Star detail, Gaze,
Constellation, and Namespace pages ported from ``design/`` into ``pages/``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from chirp.testing import TestClient
from test_app import _modern_mcp_headers, _modern_mcp_params

from catalog import CATALOG, Catalog, ResolveRecord


def _embedded_error_map(html: str, element_id: str) -> dict:
    marker = f'id="{element_id}"'
    start = html.index(marker)
    open_end = html.index(">", start) + 1
    close = html.index("</script>", open_end)
    return json.loads(html[open_end:close])


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
@pytest.mark.issue(473)
class TestBrandChrome:
    async def test_static_design_assets_served(self, example_app) -> None:
        async with TestClient(example_app) as client:
            tokens = await client.get("/static/css/tokens.css")
            assert tokens.status == 200
            assert "--ink" in tokens.text
            assert "--tick" in tokens.text
            assert "--space-3" in tokens.text
            assert "--glow-brass" in tokens.text
            sky = await client.get("/static/css/atmosphere.css")
            assert sky.status == 200
            assert ".cosmos" in sky.text
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
                assert "/static/css/tokens.css" in r.text, path
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
            assert 'href="/gaze" role="menuitem" aria-current="page"' in gaze.text
            assert 'class="nav-dropdown" open' not in gaze.text
            assert 'nav-dropdown-trigger is-active' in gaze.text
            resolve = await client.get("/resolve")
            assert 'href="/resolve" role="menuitem" aria-current="page"' in resolve.text
            assert 'class="nav-dropdown" open' not in resolve.text
            console = await client.get("/console")
            assert "Skill console" in console.text
            assert "/console/html-to-pdf" in console.text

    async def test_product_dropdown_closed_connect_cta_ink_skip_link(
        self, example_app
    ) -> None:
        css = (
            Path(__file__).resolve().parents[1] / "static" / "css" / "components.css"
        ).read_text()
        assert ".nav-cta" in css
        assert "var(--ink)" in css

        async with TestClient(example_app) as client:
            gaze = await client.get("/gaze")
            assert gaze.status == 200
            assert 'href="#main"' in gaze.text
            assert 'class="skip-link"' in gaze.text
            assert 'class="btn nav-cta"' in gaze.text
            assert "@click.outside" in gaze.text
            assert "@keydown.escape.window" in gaze.text
            assert 'class="nav-dropdown" open' not in gaze.text

            star = await client.get("/star/orrery/world-time")
            assert star.status == 200
            assert 'nav-dropdown-trigger is-active' in star.text
            assert 'class="nav-dropdown" open' not in star.text


@pytest.mark.issue(494)
class TestFooterClusters:
    async def test_footer_has_three_clusters_and_brand_line(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/")
            assert r.status == 200
            footer_start = r.text.index('class="footer"')
            footer_end = r.text.index("</footer>", footer_start)
            footer = r.text[footer_start:footer_end]
            assert "Orrery · skills you point at, not install." in footer
            assert 'class="footer-cluster"' in footer
            assert 'aria-label="Loop"' in footer
            assert 'aria-label="Legal"' in footer
            assert 'aria-label="Agents"' in footer
            assert ">Loop<" in footer
            assert ">Legal<" in footer
            assert ">Agents<" in footer
            assert 'href="/gaze"' in footer
            assert 'href="/resolve"' in footer
            assert 'href="/stars"' in footer
            assert 'href="/constellations"' in footer
            assert 'href="/receipts"' in footer
            assert 'href="/security"' in footer
            assert 'href="/privacy"' in footer
            assert 'href="/terms"' in footer
            assert 'href="/contact"' in footer
            assert 'href="/connect"' in footer
            assert 'href="/llms.txt"' in footer
            assert ">Ops · console<" in footer
            assert "footer_note" not in footer
            assert "footer_meta" not in footer
            assert "gaze → resolve → call" not in footer

    async def test_page_footer_overrides_ignored(self, example_app) -> None:
        async with TestClient(example_app) as client:
            home = await client.get("/")
            assert home.status == 200
            assert "Orrery · live host" not in home.text

            connect = await client.get("/connect")
            assert connect.status == 200
            footer_start = connect.text.index('class="footer"')
            footer_end = connect.text.index("</footer>", footer_start)
            footer = connect.text[footer_start:footer_end]
            assert "Orrery · connect" not in footer
            assert "point → call → seal" not in footer

            resolve = await client.get("/resolve")
            assert resolve.status == 200
            assert "Resolver console" not in resolve.text


@pytest.mark.issue(473)
class TestCssTokenLayers:
    async def test_primitives_and_motion_beats_exist(self, example_app) -> None:
        async with TestClient(example_app) as client:
            primitives = await client.get("/static/css/primitives.css")
            assert primitives.status == 200
            for name in (".field", ".alert", ".stack", "[x-cloak]", ".table-row-link"):
                assert name in primitives.text
            motion = await client.get("/static/css/motion.css")
            assert motion.status == 200
            assert ":active" in motion.text
            assert ":focus-visible" in motion.text
            assert "var(--tick)" in motion.text


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
            assert "/static/css/tokens.css" in r.text
            assert 'class="topbar"' in r.text
            assert "orrery/world-time" in r.text
            assert "Use this when" in r.text
            assert "Example" in r.text
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
        assert "utc" in hit.blurb.lower() and "signed" in hit.blurb.lower()
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
                "/mcp/dogfood",
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
            body = json.loads(text)
            payload = body.get("payload") if isinstance(body, dict) else {}
            assert isinstance(payload, dict)
            assert payload.get("price_per_call") is None
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
                "/mcp/dogfood",
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
        assert {h.name for h in consts} >= {"orrery/stale-proof"}
        assert all(not h.name.startswith("acme/") for h in consts)
        assert all(h.kind == "constellation" for h in consts)

        acme_consts = CATALOG.list_constellations(node="acme")
        assert {h.name for h in acme_consts} >= {
            "acme/release-gate",
            "acme/launch-gate",
        }

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
            assert "orrery/stale-proof" in text
            assert "acme/launch-gate" not in text

            acme_listed = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "id": 24,
                    "params": {
                        "_meta": {
                            "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                            "io.modelcontextprotocol/clientCapabilities": {},
                        },
                        "name": "gaze_list_constellations",
                        "arguments": {"node": "acme"},
                    },
                },
                headers={
                    "content-type": "application/json",
                    "mcp-protocol-version": "2026-07-28",
                    "mcp-method": "tools/call",
                    "mcp-name": "gaze_list_constellations",
                },
            )
            acme_text = json.loads(acme_listed.text)["result"]["content"][0]["text"]
            assert "acme/launch-gate" in acme_text


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
            assert "syncUi" in attr
            assert "filterKind" in attr
            assert "renderHit" not in attr
            assert "innerHTML" not in attr

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
            r = await client.get("/constellations?name=acme/launch-gate")
            assert r.status == 200
            assert "data-constellation" in r.text
            assert "<svg" in r.text
            assert "acme/launch-gate" in r.text
            assert "secret-scan" in r.text
            assert "html-to-pdf*" in r.text
            assert "Composite receipt" in r.text
            assert "Reliability console" in r.text
            assert "What to pass" in r.text
            assert "What you get" in r.text
            # Run-contract IO appears above the SVG.
            assert r.text.index("What to pass") < r.text.index("data-constellation")


@pytest.mark.issue(334)
class TestConstellationCatalogIndex:
    async def test_index_lists_multiple_constellations(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/constellations")
            assert r.status == 200
            assert "Explore Constellations" in r.text or "Constellations" in r.text
            assert "acme/launch-gate" in r.text
            assert "orrery/stale-proof" in r.text
            assert 'href="/constellations?name=' in r.text
            assert "<svg" not in r.text

    async def test_detail_renders_from_index_link(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/constellations?name=acme/launch-gate")
            assert r.status == 200
            assert "data-constellation" in r.text
            assert "acme/launch-gate" in r.text


@pytest.mark.issue(220)
class TestConstellationRunContracts:
    async def test_constellation_page_shows_pass_and_get(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/constellations?name=orrery/stale-proof")
            assert r.status == 200
            assert "What to pass" in r.text
            assert "What you get" in r.text
            assert "source_digest" in r.text
            assert "world-time → source-watch → seal" in r.text

    async def test_connect_mentions_constellations_for_agents(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/connect")
            assert r.status == 200
            assert "Constellations for agents" in r.text
            assert "gaze_describe" in r.text
            assert "explain_policy" in r.text

    async def test_connect_board_memo_continue_run_worked_example(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/connect")
            assert r.status == 200
            assert "orrery/board-memo" in r.text
            assert "continue_run" in r.text
            assert "audience-choice" in r.text

    async def test_explain_policy_mcp_returns_card_aligned_fields(self, example_app) -> None:
        async with TestClient(example_app) as client:
            called = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "id": 220,
                    "params": _modern_mcp_params(
                        name="explain_policy",
                        arguments={"name": "acme/launch-gate"},
                    ),
                },
                headers=_modern_mcp_headers("tools/call", "explain_policy"),
            )
            text = json.loads(called.text)["result"]["content"][0]["text"]
            assert "graph_summary" in text
            assert "dispositions" in text
            assert "input_schema" in text
            assert "run_contract" in text

    async def test_run_tool_schema_mentions_doc_bundle(self, example_app) -> None:
        async with TestClient(example_app) as client:
            listed = await client.post(
                "/mcp/dogfood",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/list",
                    "id": 221,
                    "params": _modern_mcp_params(),
                },
                headers=_modern_mcp_headers("tools/list"),
            )
            tools = {t["name"]: t for t in json.loads(listed.text)["result"]["tools"]}
            run = tools["run"]
            assert "pages" in run["description"].lower() or "bundle" in run["description"].lower()
            props = run["inputSchema"]["properties"]
            assert {"pages", "links", "examples"} <= set(props)


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
                "/mcp/dogfood",
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
                "/mcp/dogfood",
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
                "/mcp/dogfood",
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
                "/mcp/dogfood",
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
                "/mcp/dogfood",
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
                "/mcp/dogfood",
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
        assert "prove" in (rec.description or "").lower()
        assert "stale" in (rec.description or "").lower()
        described = CATALOG.describe("orrery/stale-proof")
        assert described["kind"] == "constellation"
        blurbs = CATALOG.match("stale proof live utc", node="public")
        assert any(h.name == "orrery/stale-proof" for h in blurbs)
        hit = next(h for h in blurbs if h.name == "orrery/stale-proof")
        assert "live" in hit.blurb.lower() or "stale" in hit.blurb.lower()

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

    @pytest.mark.issue(383)
    async def test_namespace_create_control_enabled(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/namespaces")
            assert r.status == 200
            assert "Coming soon" not in r.text
            assert 'disabled\n      aria-disabled="true"' not in r.text
            assert 'action="/namespaces"' in r.text
            assert "Create namespace" in r.text
            assert 'id="namespace_id"' in r.text

    @pytest.mark.issue(383)
    async def test_namespace_no_dead_hash_cta(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/namespaces")
            assert r.status == 200
            assert 'href="#"' not in r.text

    @pytest.mark.issue(383)
    async def test_namespace_create_success_path_documented(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/namespaces?created=acme")
            assert r.status == 200
            assert "/gaze?node=acme" in r.text
            assert "/resolve?name=acme/demo" in r.text
            assert "path prefix" in r.text.lower()
            assert "{id}/*" in r.text

    @pytest.mark.issue(383)
    async def test_namespace_create_api_success(self, example_app) -> None:
        from namespaces import reset_namespace_store

        reset_namespace_store()
        try:
            async with TestClient(example_app) as client:
                response = await client.post("/api/namespaces", json={"id": "widgetco"})
            assert response.status == 201
            body = json.loads(response.text)
            assert body["id"] == "widgetco"
        finally:
            reset_namespace_store()

    @pytest.mark.issue(433)
    @pytest.mark.issue(476)
    async def test_namespace_page_embeds_error_map(self, example_app) -> None:
        from pages.namespaces._errors import KNOWN

        async with TestClient(example_app) as client:
            r = await client.get("/namespaces")
            assert r.status == 200
            assert 'id="namespace-error-map"' not in r.text
            assert "createNamespace" not in r.text
            assert "this.error = body.error" not in r.text
            for code, copy in KNOWN.items():
                landed = await client.get(f"/namespaces?error={code}")
                assert landed.status == 200
                assert copy["message"] in landed.text
                assert copy["next"] in landed.text
                assert code in landed.text
                assert 'role="alert"' in landed.text
                assert 'class="alert"' in landed.text

    @pytest.mark.issue(476)
    async def test_namespace_form_is_html_post_not_alpine_fetch(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/namespaces")
        assert r.status == 200
        assert 'hx-post="/namespaces"' in r.text
        assert 'method="post"' in r.text
        assert "htmx-indicator" in r.text
        assert 'class="field"' in r.text
        assert "fetch(" not in r.text
        assert "createNamespace" not in r.text


@pytest.mark.issue(372)
class TestWalletTopUpPage:
    async def test_wallet_top_up_route_returns_200(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/wallet/top-up")
            assert r.status == 200
            assert 'class="topbar"' in r.text
            assert "Top up balance" in r.text

    async def test_wallet_top_up_uses_checkout_packs_not_per_call_stripe(
        self, example_app
    ) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/wallet/top-up")
            assert r.status == 200
            assert "/api/wallet/stripe/checkout" in r.text
            assert "starter" in r.text
            assert "standard" in r.text
            assert "premium" in r.text
            assert "no per-call PaymentIntents" in r.text
            assert "PaymentIntent" not in r.text.replace("PaymentIntents", "")

    async def test_wallet_top_up_cites_top_up_url(self, example_app) -> None:
        from commerce.errors import TOP_UP_URL

        async with TestClient(example_app) as client:
            r = await client.get("/wallet/top-up")
            assert r.status == 200
            assert TOP_UP_URL in r.text
            assert "top_up_url" in r.text
            assert "insufficient_balance" in r.text

    async def test_wallet_success_return_does_not_claim_credit(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/wallet?topup=success")
            assert r.status == 200
            assert "does not" in r.text.lower() or "not" in r.text.lower()
            assert "webhook" in r.text.lower()

    def test_insufficient_balance_error_includes_top_up_url(self) -> None:
        from commerce.errors import TOP_UP_URL, InsufficientBalanceError

        err = InsufficientBalanceError(price_per_call_cents=2, balance_cents=0)
        payload = err.to_dict()
        assert payload["code"] == "insufficient_balance"
        assert payload["top_up_url"] == TOP_UP_URL
        assert payload["top_up_url"].endswith("/wallet/top-up")

    @pytest.mark.issue(433)
    @pytest.mark.issue(477)
    async def test_wallet_top_up_embeds_error_map(self, example_app) -> None:
        from pages.wallet._errors import KNOWN

        async with TestClient(example_app) as client:
            r = await client.get("/wallet/top-up")
            assert r.status == 200
            assert 'id="wallet-error-map"' not in r.text
            assert "walletTopUp" not in r.text
            assert "startCheckout" not in r.text
            assert "this.error = body.error" not in r.text
            for code, copy in KNOWN.items():
                landed = await client.get(f"/wallet/top-up?error={code}")
                assert landed.status == 200
                assert copy["message"] in landed.text
                assert copy["next"] in landed.text
                assert code in landed.text
                assert 'role="alert"' in landed.text
                assert 'class="alert"' in landed.text

    @pytest.mark.issue(477)
    async def test_wallet_top_up_form_is_html_post_not_alpine_fetch(
        self, example_app
    ) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/wallet/top-up")
        assert r.status == 200
        assert 'hx-post="/wallet/top-up"' in r.text
        assert 'method="post"' in r.text
        assert "htmx-indicator" in r.text
        assert 'class="field"' in r.text
        assert 'class="stack"' in r.text
        assert "fetch(" not in r.text
        assert "walletTopUp" not in r.text
        assert "startCheckout" not in r.text
        assert "window.location" not in r.text


@pytest.mark.issue(433)
class TestPageErrorMaps:
    def test_wallet_known_codes_have_sentence_and_next(self) -> None:
        from pages.wallet._errors import KNOWN, describe

        expected = ("owner_id_required", "invalid_pack", "wallet_disabled")
        assert tuple(KNOWN) == expected
        for code in expected:
            copy = describe(code)
            assert copy.code == code
            assert copy.message.endswith(".")
            assert copy.next
            assert code not in copy.human_line
            assert " " in copy.next or copy.next.endswith(".")

    def test_namespace_known_codes_have_sentence_and_next(self) -> None:
        from pages.namespaces._errors import KNOWN, describe

        expected = ("invalid_slug", "reserved_slug", "duplicate_namespace")
        assert tuple(KNOWN) == expected
        for code in expected:
            copy = describe(code)
            assert copy.code == code
            assert copy.message.endswith(".")
            assert copy.next
            assert code not in copy.human_line

    def test_unknown_machine_code_keeps_generic_line_and_code(self) -> None:
        from pages.namespaces._errors import GENERIC_MESSAGE, GENERIC_NEXT, describe
        from pages.wallet._errors import GENERIC_MESSAGE as WALLET_GENERIC
        from pages.wallet._errors import GENERIC_NEXT as WALLET_NEXT
        from pages.wallet._errors import describe as wallet_describe

        ns = describe("id_required")
        assert ns.message == GENERIC_MESSAGE
        assert ns.next == GENERIC_NEXT
        assert ns.code == "id_required"
        wallet = wallet_describe("payment_id_required")
        assert wallet.message == WALLET_GENERIC
        assert wallet.next == WALLET_NEXT
        assert wallet.code == "payment_id_required"

    def test_raw_exception_strings_are_never_displayed(self) -> None:
        from pages.namespaces._errors import describe as ns_describe
        from pages.wallet._errors import describe as wallet_describe

        leak = "ValueError: checkout exploded\nTraceback (most recent call last)"
        for mapped in (wallet_describe(leak), ns_describe(leak), wallet_describe(None)):
            assert "ValueError" not in mapped.human_line
            assert "Traceback" not in mapped.human_line
            assert mapped.code == ""
            assert mapped.message
            assert mapped.next


@pytest.mark.issue(407)
class TestHomeFeedPolish:
    async def test_home_feed_quiet_empty_state(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/")
            assert r.status == 200
            assert "feed-quiet" in r.text
            assert "Quiet sky" in r.text
            assert "Waiting for an MCP" not in r.text
            assert 'sse-connect="/feed"' in r.text

    def test_feed_format_args_omits_denylisted_html(self, example_app) -> None:
        import sys

        host = sys.modules["orrery_app_under_test"]
        rendered = host.feed_format_args(
            {"html": "<p>Orion</p>", "name": "orrery/html-to-pdf"}
        )
        assert "Orion" not in rendered
        assert 'name="orrery/html-to-pdf"' in rendered

    def test_feed_format_args_truncates_long_values(self, example_app) -> None:
        import sys

        host = sys.modules["orrery_app_under_test"]
        rendered = host.feed_format_args({"intent": "x" * 200})
        assert len(rendered) <= 120
        assert rendered.endswith("…")


@pytest.mark.issue(409)
class TestHomeSkyVitalsStrip:
    async def test_home_renders_vitals_strip_with_live_snapshot(self, example_app) -> None:
        import sys

        host = sys.modules["orrery_app_under_test"]
        snapshot = host.sky_vitals.snapshot()

        async with TestClient(example_app) as client:
            r = await client.get("/")
            assert r.status == 200
            assert 'class="sky-vitals"' in r.text
            assert 'data-sky-vitals' in r.text
            assert 'data-metric="stars_live"' in r.text
            assert 'data-metric="invocations_24h"' in r.text
            assert str(snapshot["catalog"]["stars_live"]) in r.text
            assert str(snapshot["activity"]["invocations_24h"]) in r.text
            assert "Invocations (24h)" in r.text
            assert "Resolves" in r.text
            assert "Seals" in r.text
            lowered = r.text.lower()
            assert "users" not in lowered
            assert "visitors" not in lowered

    async def test_home_preserves_hero_and_feed_sections(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/")
            assert r.status == 200
            assert 'class="hero"' in r.text
            assert "Skills you" in r.text
            assert "How agents win" in r.text
            assert 'class="feed"' in r.text
            assert 'sse-connect="/feed"' in r.text
            assert "feed-quiet" in r.text


@pytest.mark.issue(431)
class TestHomeFourStepLoop:
    async def test_homepage_names_gaze_resolve_call_seal(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/")
            assert r.status == 200
            start = r.text.index('class="steps"')
            end = r.text.index("</ol>", start)
            steps = r.text[start:end]
            gaze = steps.index("<strong>Gaze</strong>")
            resolve = steps.index("<strong>Resolve</strong>")
            call = steps.index("<strong>Call</strong>")
            seal = steps.index("<strong>Seal</strong>")
            assert gaze < resolve < call < seal
            assert "<strong>Verify</strong>" not in steps
            assert "Pay only for truth" not in r.text
            assert "verifyable" not in r.text
            assert "verifiable" in r.text


@pytest.mark.issue(432)
class TestMcpCopyAdr0010:
    async def test_connect_describes_slim_mcp_not_legacy_bridge(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/connect")
            assert r.status == 200
            text = r.text
            lowered = text.lower()
            assert "legacy bridge" not in lowered
            assert "discovery only" not in lowered
            assert "slim discovery" in lowered
            assert "call_skill" in text
            assert "forwarder" in lowered
            assert "canonical" in lowered
            assert 'id="kida-demo"' in text


@pytest.mark.issue(445)
class TestGetListedConnect:
    async def test_connect_get_listed_section(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/connect")
            assert r.status == 200
            text = r.text
            assert 'id="get-listed"' in text
            assert "Get listed (newcomer shelf)" in text
            assert "index_ping" in text
            assert "rate_listing" in text

    async def test_gaze_kicker_does_not_say_route(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/gaze")
            assert r.status == 200
            head_start = r.text.index('class="console-head"')
            kicker_start = r.text.index('class="kicker"', head_start)
            kicker_open = r.text.index(">", kicker_start) + 1
            kicker = r.text[kicker_open : r.text.index("</p>", kicker_open)]
            assert "route" not in kicker.lower()
            assert "browse" in kicker.lower()
            assert "point" in kicker.lower()
            assert "install" in kicker.lower()


@pytest.mark.issue(454)
class TestGetListedHomepagePointer:
    async def test_home_points_at_get_listed_index_ping(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/")
            assert r.status == 200
            text = r.text
            assert "/connect#get-listed" in text
            assert "index_ping" in text

    async def test_for_harnesses_points_at_get_listed_index_ping(
        self, example_app
    ) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/for-harnesses")
            assert r.status == 200
            text = r.text
            assert "/connect#get-listed" in text
            assert "index_ping" in text


@pytest.mark.issue(474)
class TestChirpInjectCsp:
    def test_layout_source_has_no_cdn_script_tags(self) -> None:
        layout = (Path(__file__).resolve().parents[1] / "pages" / "_layout.html").read_text()
        assert "cdn.jsdelivr.net/npm/htmx" not in layout
        assert "cdn.jsdelivr.net/npm/alpinejs" not in layout
        assert "unpkg.com/htmx-ext-sse" not in layout

    async def test_pages_use_chirp_inject_and_local_sse(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/")
            assert r.status == 200
            assert 'data-chirp="htmx"' in r.text
            assert 'data-chirp="alpine"' in r.text
            assert "/static/htmx-ext-sse.js" in r.text
            assert "unpkg.com/htmx-ext-sse" not in r.text
            assert "cdn.jsdelivr.net/npm/alpinejs@" not in r.text

    async def test_csp_header_is_nonced_without_unsafe_eval(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/")
            csp = dict(r.headers).get("content-security-policy", "")
            assert "nonce-" in csp
            assert "unsafe-eval" not in csp
            assert "style-src" in csp
            assert "'unsafe-inline'" in csp
            assert "fonts.googleapis.com" in csp
            assert "fonts.gstatic.com" in csp


@pytest.mark.issue(475)
class TestGazeHtmxFragment:
    async def test_gaze_page_has_htmx_form_not_render_hit(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/gaze")
            assert r.status == 200
            assert 'hx-get="/gaze"' in r.text
            assert 'hx-target="#gaze-hits"' in r.text
            assert 'id="gaze-hits"' in r.text
            assert "var(--settle)" in r.text
            assert "renderHit" not in r.text
            assert "innerHTML" not in r.text
            assert "/api/gaze/match" not in r.text

    async def test_gaze_intent_is_full_page(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/gaze?intent=html+pdf")
            assert r.status == 200
            assert "<!DOCTYPE html>" in r.text
            assert 'class="console-head"' in r.text
            assert 'id="gaze-hits"' in r.text
            assert "orrery/html-to-pdf" in r.text

    async def test_gaze_hx_request_returns_hits_block_only(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get(
                "/gaze?intent=html+pdf",
                headers={"HX-Request": "true"},
            )
            assert r.status == 200
            assert "<!DOCTYPE html>" not in r.text
            assert "<html" not in r.text
            assert 'class="console-head"' not in r.text
            assert 'id="gaze-hits"' in r.text
            assert "gaze-hits" in r.text
            assert "orrery/html-to-pdf" in r.text
            assert "var(--settle)" in r.text


@pytest.mark.issue(478)
class TestResolveSettle:
    async def test_resolve_is_plain_get_with_row_links(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/resolve")
            assert r.status == 200
            assert 'action="/resolve"' in r.text
            assert 'method="get"' in r.text
            assert "onclick=" not in r.text
            assert 'class="table-row-link' in r.text
            assert 'href="/star/orrery/html-to-pdf"' in r.text
            js = await client.get("/static/motion.js")
            assert js.status == 200
            assert "function initResolve" not in js.text
            assert "settleDigest" in js.text
            assert "initConstellation" in js.text
            assert "initCopyMcp" in js.text

    async def test_lookup_settles_server_matched_digest(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/resolve?q=world-time")
            assert r.status == 200
            assert "data-resolve-matched" in r.text
            assert "row-resolved" in r.text
            assert "Resolved · world-time" in r.text
            assert "data-digest" in r.text
            assert "data-final=" in r.text
            rec = CATALOG.resolve("world-time")
            assert rec is not None
            assert rec.content_digest in r.text
            js = await client.get("/static/motion.js")
            assert "initMatchedDigest" in js.text
            assert "value-settled" in js.text
            assert "--settle" in js.text


@pytest.mark.issue(480)
class TestCatalogAlpineFilters:
    async def test_stars_catalog_uses_alpine_not_domcontentloaded(
        self, example_app
    ) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/stars")
            assert r.status == 200
            assert 'x-data="starsCatalog"' in r.text
            assert "Alpine.safeData" in r.text
            assert "DOMContentLoaded" not in r.text
            assert "data-star-search" in r.text
            assert "data-star-facet" in r.text

    async def test_constellations_catalog_uses_alpine_not_domcontentloaded(
        self, example_app
    ) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/constellations")
            assert r.status == 200
            assert 'x-data="constellationsCatalog"' in r.text
            assert "Alpine.safeData" in r.text
            assert "DOMContentLoaded" not in r.text
            assert "data-constellation-search" in r.text


@pytest.mark.issue(481)
class TestStarDetailSeal:
    def test_star_detail_template_composes_without_extends(self) -> None:
        source = (
            Path(__file__).resolve().parents[1] / "pages" / "star_detail.html"
        ).read_text()
        assert 'extends "_layout.html"' not in source
        assert "{% block content %}" in source
        assert "data-receipt" in source
        assert "verify-ok" in source

    def test_motion_keeps_star_receipt_init(self) -> None:
        js = (Path(__file__).resolve().parents[1] / "static" / "motion.js").read_text()
        assert "function initStarReceipt" in js
        assert "[data-receipt]" in js
        assert "vibrate(12)" in js

    async def test_star_page_renders_live_receipt_seal(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/star/orrery/world-time")
            assert r.status == 200
            assert "<!DOCTYPE html>" in r.text
            assert 'class="topbar"' in r.text
            assert "data-receipt" in r.text
            assert "Verified · not forged" in r.text
            assert "orrery/world-time" in r.text
            assert "Ed25519" in r.text
            motion = await client.get("/static/motion.js")
            assert motion.status == 200
            assert "function initStarReceipt" in motion.text


@pytest.mark.issue(482)
class TestMotionLoop:
    def test_feed_row_has_one_shot_arrive_class(self) -> None:
        root = Path(__file__).resolve().parents[1]
        feed = (root / "pages" / "_feed.html").read_text()
        motion = (root / "static" / "css" / "motion.css").read_text()
        assert 'class="activity-item is-arriving"' in feed
        assert ".activity-item.is-arriving" in motion
        assert "var(--settle)" in motion
        assert "function initFeedArrive" in (
            root / "static" / "motion.js"
        ).read_text()

    def test_copy_reads_flash_not_raw_ms(self) -> None:
        js = (
            Path(__file__).resolve().parents[1] / "static" / "motion.js"
        ).read_text()
        assert "function initCopyMcp" in js
        assert "function initMatchedDigest" in js
        assert "function initConstellation" in js
        assert "function initStarReceipt" in js
        assert "--flash" in js
        assert "flashMs" in js
        assert "is-copied" in js
        assert "1200" not in js
        assert "vibrate(12)" in js

    def test_load_theater_rise_is_gone(self) -> None:
        root = Path(__file__).resolve().parents[1]
        widgets = (root / "static" / "css" / "widgets.css").read_text()
        layouts = (root / "static" / "css" / "layouts.css").read_text()
        motion = (root / "static" / "css" / "motion.css").read_text()
        assert "animation: rise" not in widgets
        assert "animation: rise" not in layouts
        assert "animation: rise" not in motion
        assert ".resolve-demo" in widgets
        assert ".hero-copy" in layouts

    def test_reduced_motion_covers_press_arrive_settle_seal(self) -> None:
        css = (
            Path(__file__).resolve().parents[1]
            / "static"
            / "css"
            / "motion.css"
        ).read_text()
        assert "prefers-reduced-motion" in css
        reduce_at = css.index("@media (prefers-reduced-motion: reduce)")
        block = css[reduce_at:]
        assert ".btn:active" in block
        assert ".activity-item.is-arriving" in block
        assert "[data-digest].value-settled" in block
        assert "[data-receipt]" in block
        assert "transition: none" in block

    async def test_home_feed_and_copy_hooks_still_render(
        self, example_app
    ) -> None:
        async with TestClient(example_app) as client:
            home = await client.get("/")
            assert home.status == 200
            assert 'class="resolve-demo"' in home.text
            assert 'class="activity"' in home.text
            star = await client.get("/star/orrery/world-time")
            assert star.status == 200
            assert "data-copy-mcp" in star.text
            motion = await client.get("/static/css/motion.css")
            assert motion.status == 200
            assert "prefers-reduced-motion" in motion.text
            assert "animation: rise" not in motion.text
