"""Leaf #338 — /pricing public sky free-label honesty."""

from __future__ import annotations

import pytest
from chirp.testing import TestClient


@pytest.mark.issue(338)
class TestPricingPage:
    async def test_pricing_page_returns_200(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/pricing")
            assert r.status == 200

    async def test_pricing_distinguishes_catalog_label_from_future_terms(
        self, example_app
    ) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/pricing")
            text = r.text.lower()
            assert "catalog" in text
            assert "free" in text
            assert "not a promise" in text or "not a forever" in text
            assert "future" in text

    async def test_pricing_points_to_connect(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/pricing")
            assert 'href="/connect"' in r.text
            assert "Connect MCP" in r.text

    async def test_pricing_does_not_claim_per_call_stripe(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/pricing")
            text = r.text.lower()
            assert "no per-call card micropayments" in text
            assert "no fake seat checkout" in text
            assert "not stripe authorization on every mcp invocation" in text
