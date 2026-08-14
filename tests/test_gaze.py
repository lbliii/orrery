"""Gaze trust projection — satisfaction pills on hits (#69)."""

from __future__ import annotations

import json

import pytest
from chirp.testing import TestClient

from catalog import CATALOG
from catalog.gaze import hit_from_record, records_for_gaze_node
from catalog.models import ResolveRecord
from listings.store import InMemoryListingStore, configure_listing_store, quiet_names
from trust.satisfaction import InMemorySatisfactionStore, SatisfactionRecord, get_satisfaction_store

STAR = "orrery/world-time"


@pytest.fixture(autouse=True)
def _isolate_default_store(monkeypatch: pytest.MonkeyPatch) -> None:
    fresh = InMemorySatisfactionStore()
    monkeypatch.setattr("trust.satisfaction._default_store", fresh)


def _world_time_record() -> ResolveRecord:
    hits = CATALOG.search("world-time")
    hit = next((h for h in hits if h.name == STAR), None)
    if hit is not None:
        resolved = CATALOG.resolve(hit.name)
        if resolved is not None:
            return resolved
    return ResolveRecord(
        name=STAR,
        endpoint="mcp://orrery.lol/stars/world-time/mcp",
        content_digest="sha256:world-time-test",
        kind="star",
        oracle_ok=True,
    )


@pytest.mark.issue(69)
def test_gaze_hit_trust_includes_satisfaction_key() -> None:
    record = _world_time_record()
    wire = hit_from_record(record).as_dict()
    assert "satisfaction" in wire["trust"]
    assert wire["trust"]["satisfaction"]["quiet"] is True
    assert "oracle" in wire["trust"]


@pytest.mark.issue(69)
def test_gaze_hit_satisfaction_populated_when_store_has_live_ratings() -> None:
    record = _world_time_record()
    store = get_satisfaction_store()
    store.put(
        SatisfactionRecord(
            star_name=STAR,
            content_digest=record.content_digest,
            verdict="useful",
            created_at="2026-08-11T12:00:00Z",
            call_attempt_id="gaze-live",
        )
    )
    hit = hit_from_record(record)
    sat = hit.as_dict()["trust"]["satisfaction"]
    assert sat["quiet"] is False
    assert sat["pill_text"] == "100% useful · 1/7d"
    assert hit.as_dict()["trust"]["oracle"]["pill_text"]


@pytest.mark.issue(69)
def test_gaze_hit_satisfaction_quiet_on_digest_mismatch() -> None:
    record = _world_time_record()
    store = get_satisfaction_store()
    store.put(
        SatisfactionRecord(
            star_name=STAR,
            content_digest="sha256:stale-other-digest",
            verdict="useful",
            created_at="2026-08-11T12:00:00Z",
            call_attempt_id="gaze-stale",
        )
    )
    hit = hit_from_record(record)
    assert hit.as_dict()["trust"]["satisfaction"] == {"quiet": True}


@pytest.mark.issue(69)
async def test_api_gaze_match_includes_satisfaction(example_app) -> None:
    async with TestClient(example_app) as client:
        response = await client.get("/api/gaze/match?intent=world+time&node=public")
        assert response.status == 200
        hit = next(h for h in json.loads(response.text)["hits"] if h["name"] == STAR)
        assert hit["trust"]["satisfaction"]["quiet"] is True
        assert "pill_text" in hit["trust"]["oracle"]


@pytest.mark.issue(69)
def test_constellation_tool_hit_has_quiet_satisfaction() -> None:
    constellation = ResolveRecord(
        name="orrery/launch-gate",
        endpoint="mcp://example/launch-gate/mcp",
        content_digest="sha256:launch",
        kind="constellation",
        oracle_ok=True,
    )
    hit = hit_from_record(constellation)
    assert hit.as_dict()["trust"]["satisfaction"] == {"quiet": True}


@pytest.mark.issue(70)
def test_records_for_gaze_node_public_excludes_private(example_app) -> None:
    pool = records_for_gaze_node(CATALOG.all(), "public")
    assert pool
    assert all(r.visibility == "public" for r in pool)
    assert not any(r.name.startswith("acme/") for r in pool)


@pytest.mark.issue(70)
def test_public_gaze_match_excludes_private_namespace(example_app) -> None:
    hits = CATALOG.match("ship gate release acme", node="public")
    assert all(not h.name.startswith("acme/") for h in hits)


@pytest.mark.issue(70)
def test_public_gaze_search_excludes_private_namespace(example_app) -> None:
    searched = CATALOG.search("acme", node="public")
    assert all(not h.name.startswith("acme/") for h in searched)


@pytest.mark.issue(70)
def test_gaze_search_defaults_to_public_sky(example_app) -> None:
    searched = CATALOG.search("acme")
    assert all(not h.name.startswith("acme/") for h in searched)


@pytest.mark.issue(70)
def test_acme_node_scopes_match_and_search(example_app) -> None:
    matched = CATALOG.match("ship gate", node="acme")
    assert matched
    assert all(h.name.startswith("acme/") for h in matched)
    searched = CATALOG.search("release", node="acme")
    assert searched
    assert all(h.name.startswith("acme/") for h in searched)


@pytest.mark.issue(70)
async def test_api_gaze_search_public_node_excludes_acme(example_app) -> None:
    async with TestClient(example_app) as client:
        response = await client.get("/api/gaze/search?q=acme&node=public")
        assert response.status == 200
        body = json.loads(response.text)
        assert body["node"] == "public"
        assert all(not h["name"].startswith("acme/") for h in body["hits"])


@pytest.mark.issue(460)
def test_quiet_name_absent_from_public_gaze_present_on_resolve(example_app) -> None:
    record = CATALOG.get("new/invoice-check")
    assert record is not None
    store = InMemoryListingStore()
    store.upsert(
        listing_url="https://example.com/.well-known/orrery.json",
        listing_json={"name": "publisher/invoice-check"},
        content_digest=record.content_digest,
        live_name="new/invoice-check",
        claimed_name="publisher/invoice-check",
        endpoint=record.endpoint,
        index_tier="newcomer",
        quiet=True,
    )
    configure_listing_store(store)
    try:
        assert "new/invoice-check" in quiet_names()
        public = records_for_gaze_node(CATALOG.all(), "public")
        assert all(r.name != "new/invoice-check" for r in public)
        assert "new/invoice-check" not in [h.name for h in CATALOG.hits_for_node("public")]
        assert "new/invoice-check" not in [h.name for h in CATALOG.match("", node="public")]
        assert CATALOG.get("new/invoice-check") is not None
        assert CATALOG.resolve("new/invoice-check") is not None
    finally:
        configure_listing_store(None)


@pytest.mark.issue(475)
async def test_gaze_hx_request_is_hits_fragment_not_full_page(example_app) -> None:
    async with TestClient(example_app) as client:
        full = await client.get("/gaze?intent=html+pdf")
        frag = await client.get(
            "/gaze?intent=html+pdf",
            headers={"HX-Request": "true"},
        )
        assert full.status == 200
        assert frag.status == 200
        assert "<!DOCTYPE html>" in full.text
        assert "<!DOCTYPE html>" not in frag.text
        assert 'id="gaze-hits"' in frag.text
        assert "orrery/html-to-pdf" in frag.text
        assert 'class="console-head"' not in frag.text
