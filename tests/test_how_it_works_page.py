"""Leaf #336 — /how-it-works gaze → resolve → call → seal walkthrough."""

from __future__ import annotations

import pytest
from chirp.testing import TestClient


@pytest.mark.issue(336)
class TestHowItWorksPage:
    async def test_how_it_works_page_returns_200(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/how-it-works")
            assert r.status == 200

    async def test_how_it_works_section_anchors(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/how-it-works")
            text = r.text
            for anchor in ("id=\"gaze\"", "id=\"resolve\"", "id=\"call\"", "id=\"seal\""):
                assert anchor in text

    async def test_how_it_works_links_live_proof(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/how-it-works")
            text = r.text
            assert "Gaze" in text
            assert "Resolve" in text
            assert "Call" in text
            assert "Seal" in text
            assert 'href="/gaze"' in text
            assert "/resolve?q=orrery/html-to-pdf" in text
            assert "/stars/world-time/mcp" in text
            assert "/console/world-time" in text
            assert "/.well-known/orrery/keys.json" in text
            assert "/api/envelope/verify" in text
            assert "orrery/world-time" in text
            assert "orrery/html-to-pdf" in text

    @pytest.mark.issue(432)
    async def test_how_it_works_mcp_is_not_legacy_bridge(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/how-it-works")
            text = r.text
            lowered = text.lower()
            assert "legacy bridge" not in lowered
            assert "discovery only" not in lowered
            assert "slim discovery" in lowered
            assert "call_skill" in text
            assert "forwarder" in lowered
            assert "canonical" in lowered
