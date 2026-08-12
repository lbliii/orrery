"""Leaf #337 — /for-harnesses tree-handling rim in public language."""

from __future__ import annotations

import pytest
from chirp.testing import TestClient


@pytest.mark.issue(337)
class TestForHarnessesPage:
    async def test_for_harnesses_page_returns_200(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/for-harnesses")
            assert r.status == 200

    async def test_for_harnesses_states_hang_dont_host(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/for-harnesses")
            text = r.text.lower()
            assert "hang" in text
            assert "host" in text
            assert "don" in text and "host" in text.split("don", 1)[-1]

    async def test_for_harnesses_guides_vs_sensors(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/for-harnesses")
            text = r.text.lower()
            assert "guides" in text
            assert "sensors" in text
            assert "feedforward" in text or "feedback" in text

    async def test_for_harnesses_non_goal_swarm_vcs(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/for-harnesses")
            text = r.text.lower()
            assert "swarm vcs" in text
            assert "not agent swarm vcs" in text or "not swarm vcs" in text

    async def test_for_harnesses_links_tree_handling_rim(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/for-harnesses")
            assert "tree-handling-rim.md" in r.text
            assert "github.com/lbliii/orrery" in r.text

    async def test_for_harnesses_nav_marks_active(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/for-harnesses")
            assert 'href="/for-harnesses" role="menuitem" aria-current="page"' in r.text
