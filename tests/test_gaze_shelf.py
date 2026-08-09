"""Gaze shelf labels - shortlist caps, facets, oracle pills (#64-#66 / epic #58)."""

from __future__ import annotations

import json

import pytest
from chirp.testing import TestClient

from catalog import CATALOG, GAZE_DEFAULT_LIMIT, GAZE_MAX_LIMIT, Catalog, clamp_gaze_limit
from catalog.models import ResolveRecord


def _bulk_records(n: int) -> tuple[ResolveRecord, ...]:
    return tuple(
        ResolveRecord(
            name=f"orrery/demo-{i:03d}",
            endpoint=f"mcp://orrery.lol/stars/demo-{i:03d}/mcp",
            content_digest=f"sha256:{i:04d}",
            kind="star",
            visibility="public",
            description="demo skill for shortlist caps",
            oracle_ok=True,
            tools=("check",),
        )
        for i in range(n)
    )


@pytest.mark.issue(64)
class TestGazeShortlistCap:
    def test_clamp_defaults_and_ceiling(self) -> None:
        assert clamp_gaze_limit(None) == GAZE_DEFAULT_LIMIT
        assert clamp_gaze_limit(GAZE_DEFAULT_LIMIT) == GAZE_DEFAULT_LIMIT
        assert clamp_gaze_limit(50) == 50
        assert clamp_gaze_limit(999) == GAZE_MAX_LIMIT
        assert clamp_gaze_limit(0) == 1
        assert clamp_gaze_limit(-3) == 1

    def test_match_and_search_default_cap(self) -> None:
        cat = Catalog(_bulk_records(35))
        matched = cat.match("demo", node="public")
        searched = cat.search("demo", node="public")
        assert len(matched) == GAZE_DEFAULT_LIMIT
        assert len(searched) == GAZE_DEFAULT_LIMIT

    def test_explicit_limit_raises_within_ceiling(self) -> None:
        cat = Catalog(_bulk_records(35))
        assert len(cat.match("demo", node="public", limit=25)) == 25
        assert len(cat.search("demo", node="public", limit=30)) == 30
        assert len(cat.match("demo", node="public", limit=999)) == 35

    async def test_api_match_respects_default_and_limit(self, example_app) -> None:
        async with TestClient(example_app) as client:
            defaulted = await client.get("/api/gaze/match?intent=demo&node=public")
            assert defaulted.status == 200
            body = json.loads(defaulted.text)
            assert body["status"] == "ok"
            assert "semantic router" in body["note"].lower()
            assert len(body["hits"]) <= GAZE_DEFAULT_LIMIT

            capped = await client.get("/api/gaze/match?intent=html&node=public&limit=1")
            assert capped.status == 200
            assert len(json.loads(capped.text)["hits"]) <= 1


@pytest.mark.issue(65)
class TestGazeHitFacets:
    def test_hit_as_dict_exposes_facets(self, example_app) -> None:
        hits = CATALOG.match("live utc", node="public")
        hit = next(h for h in hits if h.name == "orrery/world-time")
        wire = hit.as_dict()
        assert wire["kind"] == "star"
        assert wire["reactive"] is True
        assert wire["price_band"] == "free"
        assert wire["namespace"] == "orrery"
        assert "oracle_ok" in wire
        assert "payload" not in wire
        assert "tools" not in wire
        assert "datetime" not in wire

        pdf_hits = CATALOG.match("html pdf", node="public")
        pdf = next(h for h in pdf_hits if h.name == "orrery/html-to-pdf")
        assert pdf.as_dict()["reactive"] is False

    async def test_api_and_search_expose_facets(self, example_app) -> None:
        async with TestClient(example_app) as client:
            matched = await client.get("/api/gaze/match?intent=world+time&node=public")
            assert matched.status == 200
            hits = json.loads(matched.text)["hits"]
            wt = next(h for h in hits if h["name"] == "orrery/world-time")
            assert wt["reactive"] is True
            assert wt["namespace"] == "orrery"
            assert wt["price_band"] == "free"

            searched = await client.get("/api/gaze/search?q=world-time")
            assert searched.status == 200
            names = {h["name"] for h in json.loads(searched.text)["hits"]}
            assert "orrery/world-time" in names

    async def test_gaze_ui_has_facet_filters_not_card_grid(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/gaze")
            assert r.status == 200
            assert "filterKind" in r.text
            assert "filterReactive" in r.text
            assert "filterOracleOk" in r.text
            assert "data-reactive=" in r.text
            assert "gaze-hits" in r.text
            # No new card-grid chrome for results.
            assert 'class="card-grid"' not in r.text


@pytest.mark.issue(66)
class TestGazeOraclePills:
    def test_gaze_hit_includes_trust_oracle(self, example_app) -> None:
        for name in ("orrery/html-to-pdf", "orrery/world-time", "orrery/source-watch"):
            hit = next(h for h in CATALOG.search(name.split("/", 1)[-1]) if h.name == name)
            wire = hit.as_dict()
            assert "trust" in wire
            oracle = wire["trust"]["oracle"]
            assert "pill_text" in oracle
            assert "pill_class" in oracle
            assert "ok" in oracle
            assert wire["console_href"].startswith("/console/")
            assert "payload" not in wire

    async def test_gaze_ui_shows_oracle_and_console(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/gaze?node=public")
            assert r.status == 200
            assert "check · freeze · smoke" in r.text or "unscored" in r.text
            assert "/console/html-to-pdf" in r.text or "/console/world-time" in r.text
            assert "orrery/html-to-pdf" in r.text

    async def test_api_gaze_match_oracle_field(self, example_app) -> None:
        async with TestClient(example_app) as client:
            r = await client.get("/api/gaze/match?intent=html+pdf&node=public")
            assert r.status == 200
            hit = next(h for h in json.loads(r.text)["hits"] if h["name"] == "orrery/html-to-pdf")
            assert hit["trust"]["oracle"]["pill_text"]
            assert hit["console_href"] == "/console/html-to-pdf"
