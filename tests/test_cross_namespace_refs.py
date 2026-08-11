"""Cross-namespace public star refs — documentation + dogfood describe (#71)."""

from __future__ import annotations

from pathlib import Path

import pytest

from catalog import CATALOG
from catalog.agent_card import require_card
from catalog.constellation import policy_for

OPS_DOC = Path("docs/operations/cross-namespace-public-refs.md")
CROSS_NAMESPACE_PHRASE = "cross-namespace"
PUBLIC_REF_RULE = "public star"


@pytest.mark.issue(71)
def test_ops_doc_exists_and_states_rule() -> None:
    assert OPS_DOC.is_file()
    text = OPS_DOC.read_text(encoding="utf-8").lower()
    assert CROSS_NAMESPACE_PHRASE.replace("-", " ") in text or CROSS_NAMESPACE_PHRASE in text
    assert "private" in text and "public" in text
    assert "acme/launch-gate" in text
    assert "orrery/html-to-pdf" in text
    assert "0004" in text
    assert "no fake private sky" in text or "does not cover" in text


@pytest.mark.issue(71)
def test_launch_gate_policy_footnote_documents_public_ref() -> None:
    graph = policy_for("acme/launch-gate")
    assert graph is not None
    footnote = graph.footnote.lower()
    assert "public" in footnote
    assert "orrery/html-to-pdf" in footnote
    assert "acme" in footnote


@pytest.mark.issue(71)
def test_launch_gate_agent_card_mentions_cross_namespace_rule() -> None:
    card = require_card("acme/launch-gate")
    blob = " ".join(
        [
            card.summary,
            *card.use_when,
            card.graph_summary or "",
        ]
    ).lower()
    assert PUBLIC_REF_RULE.replace(" ", "") in blob.replace(" ", "") or "public" in blob
    assert "acme" in blob
    assert card.member_stars
    public_members = [m for m in card.member_stars if str(m["name"]).startswith("orrery/")]
    private_members = [m for m in card.member_stars if str(m["name"]).startswith("acme/")]
    assert public_members
    assert private_members


@pytest.mark.issue(71)
def test_gaze_describe_includes_cross_namespace_copy(example_app) -> None:
    described = CATALOG.describe("acme/launch-gate")
    assert described["status"] == "ok"
    card = described["agent_card"]
    assert isinstance(card, dict)
    use_when = " ".join(card.get("use_when", [])).lower()
    summary = str(card.get("summary", "")).lower()
    assert "public" in use_when or "public" in summary
    members = card.get("member_stars") or []
    names = {str(m.get("name", "")) for m in members}
    assert "orrery/html-to-pdf" in names
    assert any(name.startswith("acme/") for name in names)
