"""Recall@k harness for flagged gaze retrieval (#467).

Measures relevant-set recall in the top-k shortlist. Never mandates that
``hits[0]`` is a specific SKU.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from catalog import CATALOG
from catalog.retrieval import configure_retriever

_FIXTURE_PATH = Path(__file__).resolve().parent / "gaze-retrieval.v1.json"


def _load_suite() -> dict[str, Any]:
    payload = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    assert payload.get("version") == 1
    fixtures = payload.get("fixtures")
    assert isinstance(fixtures, list) and fixtures
    return payload


def recall_at_k(
    fixtures: list[dict[str, Any]],
    *,
    k: int,
) -> float:
    """Macro-average |relevant ∩ top-k| / |relevant|. Order inside k is free."""
    found = 0
    relevant = 0
    for fixture in fixtures:
        expect = list(fixture.get("expect") or [])
        if not expect:
            continue
        node = str(fixture.get("node") or "public")
        names = [hit.name for hit in CATALOG.match(str(fixture["intent"]), node=node)]
        top = names[:k]
        relevant += len(expect)
        found += sum(1 for name in expect if name in top)
    if relevant == 0:
        return 1.0
    return found / relevant


@pytest.fixture(autouse=True)
def _reset_retriever() -> None:
    configure_retriever(None)
    yield
    configure_retriever(None)


@pytest.mark.issue(467)
def test_retrieval_suite_has_relevant_sets(example_app) -> None:
    del example_app
    suite = _load_suite()
    assert int(suite.get("k") or 3) == 3
    for fixture in suite["fixtures"]:
        expect = list(fixture.get("expect") or [])
        assert expect, "retrieval fixtures are positives only"
        assert len(expect) <= 3


@pytest.mark.issue(467)
def test_recall_at_k_flag_on_at_least_baseline(
    example_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    del example_app
    suite = _load_suite()
    k = int(suite.get("k") or 3)
    fixtures = list(suite["fixtures"])

    monkeypatch.delenv("ORRERY_GAZE_RETRIEVAL", raising=False)
    baseline = recall_at_k(fixtures, k=k)
    monkeypatch.setenv("ORRERY_GAZE_RETRIEVAL", "1")
    flagged = recall_at_k(fixtures, k=k)

    assert 0.0 <= baseline <= 1.0
    assert flagged >= baseline
