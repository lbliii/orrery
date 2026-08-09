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

_META_PROTOCOL_VERSION = "io.modelcontextprotocol/protocolVersion"
N_DOGFOOD_SKILLS = 5


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


@pytest.mark.issue(10)
@pytest.mark.issue(11)
class TestOrreryHostFoundation:
    async def test_host_mounts_n_skills_and_surfaces(self, example_app) -> None:
        assert N_DOGFOOD_SKILLS == 5
        async with TestClient(example_app) as client:
            home = await client.get("/")
            assert home.status == 200
            assert "Orrery" in home.text
            assert "gaze" in home.text
            assert "resolve" in home.text
            assert "star" in home.text
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
            assert names == {"gaze", "resolve", "html-to-pdf", "world-time", "launch-gate"}

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
                "resolve_name",
                "convert",
                "health",
                "fetch",
                "get",
                "answer",
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
        import dogfood
        from dogfood import DOGFOOD_CORPUS

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

        receipt = run_publish_gate(example_app, DOGFOOD_CORPUS)
        assert receipt.passed, receipt.to_dict()
        assert receipt.smoke is not None
        assert receipt.smoke.passed


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
        spec = importlib.util.spec_from_file_location(
            "orrery_app_oracle_test", root / "app.py"
        )
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
