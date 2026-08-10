"""Constellation detail — a drawn policy graph over stars.

Resolves ``?name=`` (defaults to the demo ``acme/launch-gate``) and renders the
gate/loop/fan-in graph and composite receipt from ``design/constellation.html``.
Surfaces Agent Card run-contract IO ("What to pass" / "What you get") above the
SVG (#220). Backs GitHub epic #7 (Constellations / Policy).
"""

from __future__ import annotations

from chirp import Page, Request

from catalog import CATALOG
from catalog.agent_card import card_for
from catalog.constellation import policy_for

_DEFAULT = "acme/launch-gate"


def get(request: Request) -> Page:
    name = (request.query.get("name") or _DEFAULT).strip()
    rec = CATALOG.resolve(name)
    if rec is None or rec.kind != "constellation":
        rec = CATALOG.get(_DEFAULT)
    policy = policy_for(rec.name)
    if policy is None:
        policy = policy_for(_DEFAULT)
    assert policy is not None
    card = rec.agent_card or card_for(rec.name)
    return Page(
        "constellations/page.html",
        "content",
        page_block_name="content",
        rec=rec,
        policy=policy,
        card=card,
        pass_inputs=() if card is None else card.inputs,
        get_outputs=() if card is None else card.outputs,
        graph_summary=None if card is None else card.graph_summary,
        dispositions=() if card is None or card.dispositions is None else card.dispositions,
        page_title=f"{rec.name} — Orrery",
        footer_note="Constellation graph",
        footer_meta="gates · loops · fan-in",
    )
