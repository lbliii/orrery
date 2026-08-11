"""Gaze trust projection — satisfaction pills on hits (#69)."""

from __future__ import annotations

import json

import pytest
from chirp.testing import TestClient

from catalog import CATALOG
from catalog.gaze import hit_from_record
from catalog.models import ResolveRecord
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
