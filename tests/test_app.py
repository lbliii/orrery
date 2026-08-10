"""Foundation proof — Orrery host surfaces (port of Chirp #985 dogfood).

Traces to https://github.com/lbliii/orrery/issues/10 (scaffold) and
https://github.com/lbliii/orrery/issues/11 (dogfood corpus).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any

import pytest
from chirp.skill.publish import run_publish_gate
from chirp.testing import TestClient

from pages.page import public_capability_counts

_META_PROTOCOL_VERSION = "io.modelcontextprotocol/protocolVersion"
N_DOGFOOD_SKILLS = 6


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


def _standard_mcp_headers() -> dict[str, str]:
    """MCP 2025-06-18 sends no Orrery/Chirp routing headers."""
    return {
        "content-type": "application/json",
        "mcp-protocol-version": "2025-06-18",
    }


@pytest.mark.issue(10)
@pytest.mark.issue(11)
class TestOrreryHostFoundation:
    async def test_host_mounts_n_skills_and_surfaces(self, example_app) -> None:
        assert N_DOGFOOD_SKILLS == 6
        async with TestClient(example_app) as client:
            home = await client.get("/")
            assert home.status == 200
            assert "Orrery" in home.text
            assert "gaze" in home.text
            assert "resolve" in home.text
            assert "star" in home.text
            star_count, constellation_count = public_capability_counts()
            assert f"{star_count} Stars" in home.text
            assert f"{constellation_count} constellations" in home.text
            assert "direct MCP" in home.text
            # Branded page uses inline <style> + Google Fonts; default secure_stack
            # CSP blanked production until style-src/font-src were relaxed.
            csp = dict(home.headers).get("content-security-policy", "")
            assert "style-src" in csp
            assert "'unsafe-inline'" in csp
            assert "fonts.googleapis.com" in csp
            assert "fonts.gstatic.com" in csp

            discovery = await client.get("/skills")
            assert discovery.status == 200
            body = json.loads(discovery.text)
            names = {entry["name"] for entry in body["skills"]}
            assert names == {
                "gaze",
                "resolve",
                "html-to-pdf",
                "world-time",
                "source-watch",
                "launch-gate",
            }

            console = await client.get("/console")
            assert console.status == 200
            assert "gaze" in console.text

            detail = await client.get("/console/gaze")
            assert detail.status == 200
            assert "gaze_match" in detail.text

    async def test_aggregated_mcp_lists_and_invokes_dogfood_tools(self, example_app) -> None:
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
            assert listed.status == 200
            tool_names = {t["name"] for t in json.loads(listed.text)["result"]["tools"]}
            assert tool_names == {
                "gaze_match",
                "gaze_search",
                "gaze_describe",
                "gaze_list_constellations",
                "coverage_check",
                "resolve_name",
                "convert",
                "submit",
                "result",
                "health",
                "fetch",
                "get",
                "answer",
                "observe",
                "diff",
                "source_watch_answer",
                "run",
                "status",
                "explain_policy",
            }

            called = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "id": 2,
                    "params": _modern_mcp_params(
                        name="gaze_match",
                        arguments={"intent": "html pdf convert", "node": "public"},
                    ),
                },
                headers=_modern_mcp_headers("tools/call", "gaze_match"),
            )
            assert called.status == 200
            text = json.loads(called.text)["result"]["content"][0]["text"]
            assert "orrery/html-to-pdf" in text

    async def test_standard_2025_streamable_http_header_needs_no_body_meta_or_routing_headers(
        self, example_app
    ) -> None:
        """A deployment smoke test using the public connect-page wire shape (#150)."""
        async with TestClient(example_app) as client:
            initialized = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "id": 149,
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "orrery-smoke", "version": "1"},
                    },
                },
                headers=_standard_mcp_headers(),
            )
            assert initialized.status == 200
            init_body = json.loads(initialized.text)
            assert init_body["id"] == 149
            assert init_body["result"]["protocolVersion"] == "2025-06-18"

            listed = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/list",
                    "id": 150,
                },
                headers=_standard_mcp_headers(),
            )
            assert listed.status == 200
            body = json.loads(listed.text)
            assert body["id"] == 150
            assert {tool["name"] for tool in body["result"]["tools"]} >= {"gaze_match", "convert"}

            called = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "id": 151,
                    "params": {
                        "name": "gaze_match",
                        "arguments": {"intent": "html pdf convert", "node": "public"},
                    },
                },
                headers=_standard_mcp_headers(),
            )
            assert called.status == 200
            assert "orrery/html-to-pdf" in json.loads(called.text)["result"]["content"][0]["text"]

    async def test_agent_invocation_streams_on_home_feed(self, example_app) -> None:
        async with TestClient(example_app) as client:

            async def call_after_delay() -> None:
                await asyncio.sleep(0.1)
                await client.post(
                    "/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "method": "tools/call",
                        "id": 3,
                        "params": _modern_mcp_params(
                            name="convert",
                            arguments={"html": "<p>Orion</p>"},
                        ),
                    },
                    headers=_modern_mcp_headers("tools/call", "convert"),
                )
                await asyncio.sleep(0.15)

            task = asyncio.create_task(call_after_delay())
            result = await client.sse("/feed", max_events=1, timeout=2.0)
            await task

            assert result.status == 200
            assert result.events
            event = result.events[0]
            assert (event.event or "message") == "message"
            assert "convert" in event.data
            assert "Orion" in event.data

    def test_dogfood_skills_pass_publish_oracle(
        self, example_app, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import sys

        from chirp.skill.console import ReliabilityStore

        import dogfood
        from catalog.sync import refresh_catalog
        from dogfood import DOGFOOD_CORPUS
        from trust.oracle import record_skill_scores_from_registry

        # Publish gate re-imports paths; keep world-time deterministic.
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
        assert dogfood.fetch_live_utc()["datetime"] == "2026-08-08T12:00:00"

        host = sys.modules["orrery_app_under_test"]
        # Mirror boot: catalog must exist before gaze/resolve smoke prompts.
        refresh_catalog(host.star_registry, host.direct_star_skills, receipt=None)
        receipt = run_publish_gate(example_app, DOGFOOD_CORPUS)
        assert receipt.passed, receipt.to_dict()
        assert receipt.smoke is not None
        assert receipt.smoke.passed

        scores = ReliabilityStore()
        recorded = record_skill_scores_from_registry(scores, receipt.smoke, host.registry)
        assert recorded["html-to-pdf"].status == "pass"
        assert recorded["html-to-pdf"].total == 1
        assert recorded["gaze"].total == 1
        assert recorded["launch-gate"].total == 3
        assert recorded["html-to-pdf"].total != recorded["launch-gate"].total


@pytest.mark.issue(34)
class TestPublishOracleSurface:
    async def test_resolve_shows_unscored_when_publish_skipped(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/resolve")
            assert r.status == 200
            assert "unscored" in r.text
            assert "sha256:" in r.text

    def test_oracle_ok_after_publish_gate(
        self, example_app, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ORRERY_SKIP_PUBLISH", raising=False)
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
        import importlib.util
        import sys
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        for name in list(sys.modules):
            if name.startswith("orrery_app_") or name == "dogfood":
                sys.modules.pop(name, None)
        spec = importlib.util.spec_from_file_location("orrery_app_oracle_test", root / "app.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(root))
        try:
            spec.loader.exec_module(module)
        finally:
            with contextlib.suppress(ValueError):
                sys.path.remove(str(root))

        from catalog import CATALOG
        from trust.oracle import oracle_for

        pdf = CATALOG.resolve("orrery/html-to-pdf")
        assert pdf is not None
        assert pdf.content_digest.startswith("sha256:")
        assert pdf.oracle_ok is True
        assert oracle_for(pdf).pill_text == "check · freeze · smoke"

        wt = CATALOG.resolve("orrery/world-time")
        assert wt is not None
        assert wt.oracle_ok is True
        assert oracle_for(wt).pill_text == "check · freeze · smoke"

        # Per-skill console scores — not one host-wide report stamped on every star.
        pdf_score = module.scores.get("html-to-pdf")
        gate_score = module.scores.get("launch-gate")
        assert pdf_score.status == "pass"
        assert pdf_score.total == 1
        assert gate_score.status == "pass"
        assert gate_score.total == 3
        assert pdf_score.label != gate_score.label

    def test_host_ok_ignores_smoke_stage_failure(self) -> None:
        from chirp.skill.publish import (
            STAGE_CHECK,
            STAGE_FREEZE,
            STAGE_SMOKE,
            PublishReceipt,
            StageResult,
        )
        from chirp.skill.smoke import SmokeReport, SmokeResult, SmokeVerdict

        from trust import oracle as oracle_mod
        from trust.oracle import OracleView, configure_oracle, oracle_for

        class _Rec:
            name = "orrery/html-to-pdf"
            kind = "star"

        smoke = SmokeReport(
            results=(
                SmokeResult(
                    prompt_id="pdf-convert-smoke",
                    tool="convert",
                    verdict=SmokeVerdict(passed=True, reason="faithful"),
                    engine_payload={"pages": 1},
                    answer="ok pages application/pdf bytes_hint",
                ),
            )
        )
        receipt = PublishReceipt(
            passed=False,
            stages=(
                StageResult(STAGE_CHECK, True, "ok"),
                StageResult(STAGE_FREEZE, True, "ok"),
                StageResult(STAGE_SMOKE, False, "1 prompt failed"),
            ),
            smoke=smoke,
        )
        configure_oracle(receipt=receipt, scores=None, corpus_ok={})
        try:
            view = oracle_for(_Rec())  # type: ignore[arg-type]
            assert isinstance(view, OracleView)
            assert view.host_ok is True
            assert view.skill_ok is True
            assert view.ok is True
            assert view.pill_text == "check · freeze · smoke"
        finally:
            configure_oracle(receipt=None, scores=None, corpus_ok={})
            # Restore module globals used by other tests that re-import app.
            oracle_mod._receipt = None
            oracle_mod._scores = None
            oracle_mod._corpus_ok = {}


@pytest.mark.issue(52)
class TestDirectStarMcpEndpoints:
    async def test_direct_star_endpoints_expose_canonical_tool_names(self, example_app) -> None:
        expected = {
            "/stars/html-to-pdf/mcp": {"convert", "submit", "result", "health"},
            "/stars/csv-report/mcp": {"submit", "result"},
            "/stars/image-transform/mcp": {"submit", "result"},
            "/stars/world-time/mcp": {"fetch", "get", "answer"},
            "/stars/source-watch/mcp": {"observe", "diff", "answer"},
        }
        async with TestClient(example_app) as client:
            for path, names in expected.items():
                response = await client.post(
                    path,
                    json={
                        "jsonrpc": "2.0",
                        "method": "tools/list",
                        "id": 52,
                        "params": _modern_mcp_params(),
                    },
                    headers=_modern_mcp_headers("tools/list"),
                )
                assert response.status == 200, path
                body = json.loads(response.text)
                assert {tool["name"] for tool in body["result"]["tools"]} == names

    async def test_direct_source_watch_uses_unprefixed_answer(self, example_app) -> None:
        async with TestClient(example_app) as client:
            response = await client.post(
                "/stars/source-watch/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "id": 53,
                    "params": _modern_mcp_params(
                        name="answer",
                        arguments={
                            "question": "What deployment guidance is current?",
                            "source": "python-release-notes",
                        },
                    ),
                },
                headers=_modern_mcp_headers("tools/call", "answer"),
            )
            assert response.status == 200
            text = json.loads(response.text)["result"]["content"][0]["text"]
            assert "source-watch" in text
            assert "live_at_call" in text
