"""L3 eval health composite on gaze trust (#120)."""

from __future__ import annotations

import json

import pytest
from chirp.skill.publish import STAGE_CHECK, STAGE_FREEZE, PublishReceipt, StageResult
from chirp.testing import TestClient

from catalog import CATALOG
from catalog.gaze import eval_health_for, hit_from_record
from catalog.models import ResolveRecord
from trust.oracle import configure_oracle, oracle_for
from trust.satisfaction import (
    InMemorySatisfactionStore,
    SatisfactionRecord,
    get_satisfaction_store,
    satisfaction_pill_for,
)

STAR = "orrery/world-time"
LIVE_DIGEST = "sha256:live-digest"
OLD_DIGEST = "sha256:old-digest"


@pytest.fixture(autouse=True)
def _isolate_default_store(monkeypatch: pytest.MonkeyPatch) -> None:
    fresh = InMemorySatisfactionStore()
    monkeypatch.setattr("trust.satisfaction._default_store", fresh)


def _world_time_record(*, digest: str = LIVE_DIGEST) -> ResolveRecord:
    hits = CATALOG.search("world-time")
    hit = next((h for h in hits if h.name == STAR), None)
    if hit is not None:
        resolved = CATALOG.resolve(hit.name)
        if resolved is not None:
            return ResolveRecord(
                name=resolved.name,
                endpoint=resolved.endpoint,
                content_digest=digest,
                kind=resolved.kind,
                oracle_ok=resolved.oracle_ok,
            )
    return ResolveRecord(
        name=STAR,
        endpoint="mcp://orrery.lol/stars/world-time/mcp",
        content_digest=digest,
        kind="star",
        oracle_ok=True,
    )


def _seed_rating(*, digest: str = LIVE_DIGEST, attempt: str = "attempt-1") -> None:
    get_satisfaction_store().put(
        SatisfactionRecord(
            star_name=STAR,
            content_digest=digest,
            verdict="useful",
            created_at="2026-08-11T12:00:00Z",
            call_attempt_id=attempt,
        )
    )


@pytest.mark.issue(120)
def test_eval_health_quiet_when_empty() -> None:
    record = _world_time_record()
    wire = hit_from_record(record).as_dict()
    assert wire["trust"]["eval_health"] == {"quiet": True}
    assert "useful_pct" not in wire["trust"]["eval_health"]
    assert "total" not in wire["trust"]["eval_health"]


@pytest.mark.issue(120)
def test_eval_health_quiet_on_digest_mismatch() -> None:
    _seed_rating(digest=OLD_DIGEST, attempt="stale-1")
    record = _world_time_record(digest=LIVE_DIGEST)
    wire = hit_from_record(record).as_dict()
    assert wire["trust"]["eval_health"] == {"quiet": True}
    assert wire["trust"]["satisfaction"] == {"quiet": True}


@pytest.mark.issue(120)
def test_eval_health_narrative_when_demand_active() -> None:
    _seed_rating()
    record = _world_time_record()
    health = hit_from_record(record).as_dict()["trust"]["eval_health"]
    assert health["quiet"] is False
    assert "100% useful" in str(health["narrative"])
    assert health.get("demand") is True


@pytest.mark.issue(120)
def test_eval_health_oracle_pill_unchanged() -> None:
    _seed_rating()
    record = _world_time_record()
    wire = hit_from_record(record).as_dict()
    oracle = wire["trust"]["oracle"]
    assert "pill_text" in oracle
    assert wire["trust"]["satisfaction"]["pill_text"] == "100% useful · 1/7d"
    assert oracle == oracle_for(record).as_dict()


@pytest.mark.issue(120)
def test_eval_health_supply_and_demand_when_oracle_scored() -> None:
    configure_oracle(
        receipt=PublishReceipt(
            passed=True,
            stages=(
                StageResult(STAGE_CHECK, True, "ok"),
                StageResult(STAGE_FREEZE, True, "ok"),
            ),
            smoke=None,
        ),
        scores=None,
    )
    _seed_rating()
    record = _world_time_record()
    health = eval_health_for(
        oracle=oracle_for(record),
        satisfaction=satisfaction_pill_for(
            star_name=record.name,
            content_digest=record.content_digest,
        ),
    )
    assert health.quiet is False
    assert health.supply_ok is True
    assert "supply verified" in (health.narrative or "")
    assert "100% useful" in (health.narrative or "")


@pytest.mark.issue(120)
async def test_api_gaze_match_includes_eval_health(example_app) -> None:
    async with TestClient(example_app) as client:
        response = await client.get("/api/gaze/match?intent=world+time&node=public")
        assert response.status == 200
        hit = next(h for h in json.loads(response.text)["hits"] if h["name"] == STAR)
        assert hit["trust"]["eval_health"] == {"quiet": True}
        assert "oracle" in hit["trust"]
