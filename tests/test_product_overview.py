"""Product overview page — marketer door (/product)."""

from __future__ import annotations

import pytest
from chirp.testing import TestClient


@pytest.mark.issue(332)
class TestProductOverview:
    async def test_product_overview_page(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/product")
            assert r.status == 200
            assert "Skills you" in r.text and "point at" in r.text
            assert "Gaze" in r.text
            assert "Resolve" in r.text
            assert "Seal" in r.text
            assert "orrery/world-time" in r.text
            assert "orrery/source-watch" in r.text
            assert "orrery/html-to-pdf" in r.text
            assert "Not an MCP directory" in r.text
            assert "Not a skill router" in r.text
            assert "Not a swarm VCS" in r.text
            assert 'href="/connect"' in r.text
            assert "Connect MCP" in r.text
