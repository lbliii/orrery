"""Demand-side satisfaction aggregate pills (#69)."""

from __future__ import annotations

import pytest

from catalog.gaze import hit_from_record
from catalog.models import ResolveRecord
from catalog.star_page import satisfaction_for_star
from trust.satisfaction import (
    InMemorySatisfactionStore,
    SatisfactionRecord,
    aggregate_for_live_digest,
    get_satisfaction_store,
    satisfaction_pill_for,
    submit_rate,
)

STAR = "orrery/world-time"
LIVE_DIGEST = "sha256:live-digest"
OLD_DIGEST = "sha256:old-digest"


@pytest.fixture
def store() -> InMemorySatisfactionStore:
    return InMemorySatisfactionStore()


@pytest.fixture(autouse=True)
def _isolate_default_store(monkeypatch: pytest.MonkeyPatch) -> None:
    fresh = InMemorySatisfactionStore()
    monkeypatch.setattr("trust.satisfaction._default_store", fresh)


def _seed(
    store: InMemorySatisfactionStore,
    *,
    digest: str = LIVE_DIGEST,
    verdict: str = "useful",
    attempt: str = "attempt-1",
) -> None:
    store.put(
        SatisfactionRecord(
            star_name=STAR,
            content_digest=digest,
            verdict=verdict,
            created_at="2026-08-11T12:00:00Z",
            call_attempt_id=attempt,
        )
    )


@pytest.mark.issue(69)
def test_quiet_when_no_ratings(store: InMemorySatisfactionStore) -> None:
    pill = satisfaction_pill_for(
        star_name=STAR,
        content_digest=LIVE_DIGEST,
        store=store,
    )
    assert pill.quiet is True
    assert pill.as_dict() == {"quiet": True}


@pytest.mark.issue(69)
def test_compact_pill_when_ratings_match_live_digest(store: InMemorySatisfactionStore) -> None:
    _seed(store, attempt="a1")
    _seed(store, verdict="stale", attempt="a2")
    _seed(store, attempt="a3")
    _seed(store, attempt="a4")

    pill = satisfaction_pill_for(
        star_name=STAR,
        content_digest=LIVE_DIGEST,
        store=store,
    )
    assert pill.quiet is False
    assert pill.pill_text == "75% useful · 4/7d"
    assert pill.useful_pct == 75
    assert pill.total == 4


@pytest.mark.issue(69)
def test_digest_mismatch_is_quiet(store: InMemorySatisfactionStore) -> None:
    _seed(store, digest=OLD_DIGEST, attempt="old-1")
    _seed(store, digest=OLD_DIGEST, attempt="old-2")

    agg = aggregate_for_live_digest(
        star_name=STAR,
        content_digest=LIVE_DIGEST,
        store=store,
    )
    assert agg.total == 0

    pill = satisfaction_pill_for(
        star_name=STAR,
        content_digest=LIVE_DIGEST,
        store=store,
    )
    assert pill.quiet is True


@pytest.mark.issue(69)
def test_gaze_hit_projects_satisfaction_quiet_by_default() -> None:
    record = ResolveRecord(
        name=STAR,
        endpoint="mcp://example/mcp",
        content_digest=LIVE_DIGEST,
        kind="star",
        oracle_ok=True,
    )
    hit = hit_from_record(record)
    wire = hit.as_dict()
    assert wire["trust"]["satisfaction"] == {"quiet": True}
    oracle = wire["trust"]["oracle"]
    assert "pill_text" in oracle


@pytest.mark.issue(69)
def test_gaze_hit_oracle_unchanged_with_satisfaction() -> None:
    store = get_satisfaction_store()
    _seed(store)
    record = ResolveRecord(
        name=STAR,
        endpoint="mcp://example/mcp",
        content_digest=LIVE_DIGEST,
        kind="star",
        oracle_ok=True,
    )
    hit = hit_from_record(record)
    wire = hit.as_dict()
    assert wire["trust"]["satisfaction"]["quiet"] is False
    assert wire["trust"]["satisfaction"]["pill_text"] == "100% useful · 1/7d"
    assert wire["trust"]["oracle"]["pill_text"] in {
        "check · freeze · smoke",
        "unscored",
    }


@pytest.mark.issue(69)
def test_star_page_satisfaction_helper() -> None:
    store = get_satisfaction_store()
    _seed(store, attempt="star-page")
    pill = satisfaction_for_star(STAR, LIVE_DIGEST)
    assert pill.quiet is False
    assert "useful" in (pill.pill_text or "")


@pytest.mark.issue(69)
def test_submit_rate_then_pill_reflects_live_digest(store: InMemorySatisfactionStore) -> None:
    submit_rate(
        star_name=STAR,
        content_digest=LIVE_DIGEST,
        verdict="useful",
        call_attempt_id="via-submit",
        store=store,
        verify_receipt=lambda _: True,
    )
    pill = satisfaction_pill_for(
        star_name=STAR,
        content_digest=LIVE_DIGEST,
        store=store,
    )
    assert pill.pill_text == "100% useful · 1/7d"
