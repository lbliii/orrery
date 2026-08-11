"""L5 optional agent-loop eval + evals.json export (#121).

L5 is explicitly non-gating for publish / oracle_ok. Deterministic assertions
only — no LLM judge.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from catalog import CATALOG
from stars.stale_proof.service import run

_REPO = Path(__file__).resolve().parent.parent
_PLAN_DOC = _REPO / "docs/plan/star-eval.md"
_DESIGN_DOC = _REPO / "docs/design/star-eval.md"
_L5_OPS = _REPO / "docs/operations/star-eval-l5.md"
_EVALS_JSON = _REPO / "evals/evals.json"
_EVALS_README = _REPO / "evals/README.md"

_PARABLE_INTENT = "stale answer detection"
_PARABLE_SKU = "orrery/stale-proof"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.mark.issue(121)
def test_l5_ops_doc_exists_and_states_non_gating() -> None:
    text = _read(_L5_OPS).lower()
    assert "non-gating" in text
    assert "oracle_ok" in text or "publish" in text
    assert "l5" in text
    assert "llm" in text


@pytest.mark.issue(121)
def test_plan_and_design_docs_keep_l5_out_of_publish_gate() -> None:
    plan = _read(_PLAN_DOC)
    design = _read(_DESIGN_DOC)
    for doc in (plan, design):
        lower = doc.lower()
        assert "publish gate" in lower or "oracle_ok" in doc
        assert re.search(r"l5.*interop|interop.*l5|l5 only", lower)
    assert "L0 + L1" in design or "L0+L1" in design
    assert "gate publish" in design.lower() or "oracle_ok" in design
    assert "star-eval-l5" in design or "Implemented (#121)" in design
    assert "non-gating" in plan.lower() or "Documented as non-gating" in plan


@pytest.mark.issue(121)
def test_evals_export_fixture_present() -> None:
    assert _EVALS_README.is_file()
    readme = _read(_EVALS_README).lower()
    assert "non-gating" in readme
    assert "evals.json" in readme

    payload = json.loads(_read(_EVALS_JSON))
    assert isinstance(payload.get("skill_name"), str) and payload["skill_name"]
    evals = payload.get("evals")
    assert isinstance(evals, list) and evals
    case = evals[0]
    assert case.get("prompt") and case.get("expected_output")
    expectations = case.get("expectations") or case.get("assertions") or []
    assert expectations
    joined = " ".join(str(item) for item in expectations).lower()
    assert _PARABLE_SKU in joined or "stale-proof" in joined


@pytest.mark.issue(121)
def test_parable_gaze_resolve_call_stale_proof(example_app) -> None:
    """Thin agent-loop: gaze intent → resolve → fixture-backed call."""
    del example_app
    hits = CATALOG.match(_PARABLE_INTENT, node="public", limit=20)
    top3 = [hit.name for hit in hits[:3]]
    assert _PARABLE_SKU in top3

    resolved = CATALOG.resolve(_PARABLE_SKU)
    assert resolved is not None
    assert resolved.name == _PARABLE_SKU

    result = run(
        "sha256:l5-eval-fixture",
        time_fetch=lambda: {"datetime": "2026-08-11T12:00:00Z", "source": "fixture"},
        diff_fetch=lambda source, digest: {
            "source": source,
            "status": "unchanged",
            "known_digest": digest,
            "current_digest": "sha256:current",
        },
    )
    assert result["status"] == "fresh_proof"
    assert result["utc"] == "2026-08-11T12:00:00Z"
    assert result["source_status"] == "unchanged"
    assert result["constellation"] == _PARABLE_SKU
