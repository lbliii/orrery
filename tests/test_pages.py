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
        assert {
            "orrery/html-to-pdf",
            "orrery/world-time",
            "orrery/md-linkcheck",
            "acme/release-gate",
        } <= names

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
@pytest.mark.issue(27)
class TestStarDetail:
    async def test_default_star_manifest_and_receipt(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/stars")
            assert r.status == 200
            assert "orrery/html-to-pdf@1.2.0" in r.text
            assert "mcp://orrery.dev/s/html-to-pdf" in r.text
            assert "Last Envelope" in r.text
            assert "data-receipt" in r.text
            assert 'data-copy-mcp' in r.text
            assert 'data-mcp-url="mcp://orrery.dev/s/html-to-pdf"' in r.text
            assert "Verified · not forged" in r.text
            assert "input_digest" in r.text
            assert "signature" in r.text
            assert "orrery-pdf-1" in r.text
            assert "convert" in r.text

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

    async def test_world_time_star_shows_live_copy_and_receipt(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/stars?name=orrery/world-time")
            assert r.status == 200
            assert "orrery/world-time@0.1.0" in r.text
            assert "Live at call time" in r.text
            assert "Offline clones cannot mint" in r.text
            assert "$0.03" in r.text
            assert "fetch" in r.text
            assert "Verified · not forged" in r.text
            assert "orrery-world-time-1" in r.text
            # Receipt panel omits payload (progressive disclosure on the page wire view).
            assert '"payload"' not in r.text


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

    def test_gaze_match_world_time_has_price_no_payload(self) -> None:
        hits = CATALOG.match("live utc clock now", node="public")
        names = [h.name for h in hits]
        assert "orrery/world-time" in names
        assert names[0] == "orrery/world-time"
        hit = next(h for h in hits if h.name == "orrery/world-time")
        wire = hit.as_dict()
        assert hit.price == "$0.03"
        assert "Live UTC" in hit.blurb or "call time" in hit.blurb.lower()
        assert "payload" not in wire
        assert "datetime" not in wire
        assert "clone_warning" not in wire

    def test_resolve_world_time_returns_price(self) -> None:
        rec = CATALOG.resolve("orrery/world-time")
        assert rec is not None
        assert rec.price_per_call == "$0.03"
        assert rec.tools == ("fetch", "get", "answer")
        assert "payload" not in rec.as_dict()

    async def test_api_resolve_world_time_price(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/api/resolve?name=orrery/world-time")
            assert r.status == 200
            body = json.loads(r.text)
            assert body["name"] == "orrery/world-time"
            assert body["price_per_call"] == "$0.03"
            assert body["endpoint"] == "mcp://orrery.dev/s/world-time"
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
            assert "$0.03" in text
            assert "fetch" in text
            assert "live_at_call" not in text
            assert "clone_warning" not in text


@pytest.mark.issue(26)
@pytest.mark.issue(27)
@pytest.mark.issue(35)
class TestEnvelopeVerifyAndPdfStub:
    def test_signed_convert_receipt_verifies(self) -> None:
        from dogfood import signed_convert_receipt, verify_receipt

        receipt, verified = signed_convert_receipt()
        assert verified is True
        assert receipt["tool"] == "convert"
        assert receipt["key_id"] == "orrery-pdf-1"
        assert receipt["payload"]["content_type"] == "application/pdf"
        assert receipt["payment_id"]
        assert receipt["price_per_call"] == "$0.02"
        assert verify_receipt(receipt) is True

    def test_tampered_receipt_fails_closed(self) -> None:
        from dogfood import signed_convert_receipt, verify_receipt

        receipt, _ = signed_convert_receipt()
        forged = dict(receipt)
        forged["payload"] = {"pages": 999, "bytes_hint": 1, "content_type": "application/pdf"}
        assert verify_receipt(forged) is False

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
            assert ok_body["price_per_call"] == "$0.02"
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

    async def test_star_page_invokes_charge_stub(self, example_app, caplog) -> None:
        import logging

        async with TestClient(example_app) as client:
            with caplog.at_level(logging.WARNING, logger="orrery.commerce"):
                r = await client.get("/stars")
            assert r.status == 200
            assert "payment_id" in r.text
            assert "price_per_call" in r.text
            assert "$0.02" in r.text
            assert "commerce.charge_stub" in caplog.text

    async def test_resolve_and_gaze_include_price(self, example_app) -> None:
        async with TestClient(example_app) as client:
            resolve = await client.get("/api/resolve?name=html-to-pdf")
            assert resolve.status == 200
            assert json.loads(resolve.text)["price_per_call"] == "$0.02"

            gaze = await client.get("/api/gaze/match?intent=html+pdf")
            assert gaze.status == 200
            hits = json.loads(gaze.text)["hits"]
            pdf_hits = [h for h in hits if h["name"] == "orrery/html-to-pdf"]
            assert pdf_hits
            assert pdf_hits[0]["price"] == "$0.02"


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


@pytest.mark.issue(22)
class TestGazeCatalog:
    def test_match_ranks_html_pdf_intent(self) -> None:
        hits = CATALOG.match("html pdf convert", node="public")
        names = [h.name for h in hits]
        assert "orrery/html-to-pdf" in names
        assert names[0] == "orrery/html-to-pdf"
        hit = hits[0]
        assert hit.kind == "star"
        assert hit.endpoint
        assert "payload" not in hit.as_dict()
        assert "tools" not in hit.as_dict()

    def test_match_namespace_node_scopes_acme(self) -> None:
        hits = CATALOG.match("ship gate", node="acme")
        assert hits
        assert all(h.name.startswith("acme/") for h in hits)

    def test_search_and_describe_and_list_constellations(self) -> None:
        searched = CATALOG.search("linkcheck")
        assert any(h.name == "orrery/md-linkcheck" for h in searched)

        described = CATALOG.describe("orrery/html-to-pdf")
        assert described["status"] == "ok"
        assert described["tools"] == ["convert", "health"]
        assert described["price_per_call"] == "$0.02"

        consts = CATALOG.list_constellations()
        assert {h.name for h in consts} >= {"acme/release-gate", "acme/launch-gate"}
        assert all(h.kind == "constellation" for h in consts)

    def test_describe_miss(self) -> None:
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
            assert "mcp://orrery.dev/gaze" in r.text
            assert "orrery/html-to-pdf" in r.text
            assert "orrery/world-time" in r.text
            assert "orrery/md-linkcheck" in r.text
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
            assert "const pill" in attr

    async def test_api_gaze_match(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/api/gaze/match?intent=link+docs&node=public")
            assert r.status == 200
            body = json.loads(r.text)
            assert body["status"] == "ok"
            names = [h["name"] for h in body["hits"]]
            assert "orrery/md-linkcheck" in names


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
