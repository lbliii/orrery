"""Leaf #333 — /receipts Envelope verify explainer."""

from __future__ import annotations

import pytest
from chirp.testing import TestClient


@pytest.mark.issue(333)
class TestReceiptsPage:
    async def test_receipts_page_returns_200(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/receipts")
            assert r.status == 200

    async def test_receipts_page_links_published_keys(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/receipts")
            assert "/.well-known/orrery/keys.json" in r.text

    async def test_receipts_page_states_verify_before_trust(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/receipts")
            text = r.text.lower()
            assert "verify before trust" in text or "verify-before-trust" in text
            assert "verify" in text
            assert "/api/envelope/verify" in r.text
