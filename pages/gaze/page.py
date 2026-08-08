"""Gaze — MCP browse/route across public sky and namespace nodes.

Server-renders nodes + hits from the shared catalog; Alpine keeps the node
switcher. ``?intent=`` / ``?node=`` refresh results via ``match``. Optional
``GET /api/gaze/match`` powers live updates from the Gaze button.
Backs GitHub epic #3 / issues #22-#24.
"""

from __future__ import annotations

from dataclasses import dataclass

from chirp import Page, Request
from chirp.server.alpine import alpine_json_config

from catalog import CATALOG, GazeHit


@dataclass(frozen=True, slots=True)
class GazeNodePanel:
    id: str
    label: str
    url: str
    scope: str
    tools_display: str
    is_constellation: bool
    hits: tuple[GazeHit, ...]
    active: bool


def get(request: Request) -> Page:
    node = (request.query.get("node") or "public").strip() or "public"
    intent = (request.query.get("intent") or request.query.get("q") or "").strip()
    nodes = CATALOG.gaze_nodes()
    node_ids = {n.id for n in nodes}
    if node not in node_ids:
        node = "public"

    display_intent = intent or "docs ship ready links"
    node_panels = tuple(
        GazeNodePanel(
            id=n.id,
            label=n.label,
            url=n.url,
            scope=n.scope,
            tools_display=" · ".join(n.tools),
            is_constellation=n.scope == "constellation",
            hits=CATALOG.hits_for_node(
                n.id,
                intent=intent if (intent and n.id == node and n.id != "docs") else "",
            ),
            active=n.id == node,
        )
        for n in nodes
    )

    return Page(
        "gaze/page.html",
        "content",
        page_block_name="content",
        page_title="Gaze — Orrery",
        footer_note="Gaze nodes",
        node_panels=node_panels,
        active_node=node,
        intent=display_intent,
        # Chirp helper: JSON lives in a <script type="application/json"> tag,
        # not inside the quoted x-data attribute (avoids attribute breakout).
        gaze_cfg=alpine_json_config(
            "gaze-cfg",
            {"node": node, "q": display_intent},
        ),
    )
