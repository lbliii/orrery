"""Constellation catalog and detail — frozen planner subgraphs over stars.

``/constellations`` lists public constellations (catalog UX akin to ``/stars``).
``/constellations?name=`` renders the policy graph and composite receipt (#334).
"""

from __future__ import annotations

from chirp import NotFound, Page, Request

from catalog import CATALOG
from catalog.agent_card import card_for
from catalog.constellation import policy_for


def get(request: Request) -> Page:
    """Render the constellation catalog or a named detail view."""
    legacy_name = (request.query.get("name") or "").strip()
    if legacy_name:
        return page_for_constellation(legacy_name)

    constellations = tuple(
        record for record in CATALOG.public_records() if record.kind == "constellation"
    )
    return Page(
        "constellations/index.html",
        "content",
        page_block_name="content",
        constellations=constellations,
        page_title="Explore Constellations — Orrery",
        footer_note="Public Constellation catalog",
        footer_meta="browse → understand → run",
    )


def page_for_constellation(name: str) -> Page:
    """Render one constellation's policy graph and run-contract IO."""
    rec = CATALOG.resolve(name)
    if rec is None or rec.kind != "constellation":
        raise NotFound(f"No constellation record for {name!r}")
    policy = policy_for(rec.name)
    if policy is None:
        raise NotFound(f"No policy graph for {rec.name!r}")
    card = rec.agent_card or card_for(rec.name)
    return Page(
        "constellations/detail.html",
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
