"""Versioned gaze intent fixtures for ``gaze_match`` ranking regression (#226).

Asserts shortlists only — never a single forced winner. Each fixture lists
SKUs that must appear somewhere in the top-3 shortlist (order free). Negative
fixtures use an empty ``expect_top3`` and require no *strong* hit
(score < ``strong_min_score`` from the fixture file).

Adding intents when shipping a new star
---------------------------------------
1. Register the star's Agent Card (``example_intents``, ``use_when``, summary).
2. Append ≥1 positive fixture to ``tests/gaze-intents.v1.json`` whose
   ``expect_top3`` names that SKU (paraphrase the card intents; keep SKUs that
   already exist on the branch).
3. Optionally add a negative fixture that must not strongly match the new star.
4. Run ``uv run pytest tests/test_intent_fixtures.py -q``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from catalog import CATALOG
from catalog.gaze import _tokens, score_record

_FIXTURE_PATH = Path(__file__).resolve().parent / "gaze-intents.v1.json"
_MIN_FIXTURES = 50


def _load_suite() -> dict[str, Any]:
    payload = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    assert payload.get("version") == 1
    fixtures = payload.get("fixtures")
    assert isinstance(fixtures, list)
    return payload


@pytest.fixture(scope="module")
def intent_suite() -> dict[str, Any]:
    return _load_suite()


def test_fixture_file_has_enough_cases(intent_suite: dict[str, Any]) -> None:
    fixtures = intent_suite["fixtures"]
    assert len(fixtures) >= _MIN_FIXTURES
    positives = [f for f in fixtures if f.get("expect_top3")]
    negatives = [f for f in fixtures if not f.get("expect_top3")]
    assert positives, "need at least one positive shortlist fixture"
    assert negatives, "need at least one negative (no strong hit) fixture"


def test_fixture_skus_exist_in_catalog(example_app, intent_suite: dict[str, Any]) -> None:
    """Only reference SKUs that resolve on the current public/namespace catalog."""
    del example_app  # ensures catalog sync via app boot
    missing: list[str] = []
    for fixture in intent_suite["fixtures"]:
        node = str(fixture.get("node") or "public")
        known = {record.name for record in CATALOG.records_for_node(node)}
        for name in fixture.get("expect_top3") or []:
            if name not in known:
                missing.append(f"{name} (node={node})")
    assert not missing, f"fixture SKUs missing from catalog: {missing}"


def test_gaze_match_shortlist_fixtures(example_app, intent_suite: dict[str, Any]) -> None:
    """Run the full versioned suite once against the synced catalog."""
    del example_app
    strong_min = int(intent_suite.get("strong_min_score") or 5)
    failures: list[str] = []

    for fixture in intent_suite["fixtures"]:
        intent = str(fixture["intent"])
        expect = list(fixture.get("expect_top3") or [])
        node = str(fixture.get("node") or "public")
        if len(expect) > 3:
            failures.append(f"{intent!r}: expect_top3 longer than 3 ({expect})")
            continue

        hits = CATALOG.match(intent, node=node, limit=20)
        top3_names = [hit.name for hit in hits[:3]]

        if not expect:
            tokens = _tokens(intent)
            strong = [
                record.name
                for record in CATALOG.records_for_node(node)
                if score_record(record, tokens) >= strong_min
            ]
            if strong:
                failures.append(
                    f"negative {intent!r}: strong hits {strong} (threshold={strong_min})"
                )
            continue

        missing = [name for name in expect if name not in top3_names]
        if missing:
            failures.append(
                f"{intent!r} (node={node}): expected {expect} in top-3, got {top3_names}"
            )

    assert not failures, "intent fixture regressions:\n- " + "\n- ".join(failures)
