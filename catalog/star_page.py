"""Shared canonical human-facing Star page renderer."""

from __future__ import annotations

from chirp import NotFound, Page, Request

from catalog import CATALOG
from catalog.console_links import PUBLISHER_DIRECT_NOTE, console_href_for
from trust.oracle import oracle_for

_INTRO = {
    "cert-expiry": (
        "Watch the certificates your systems depend on and surface the ones that need "
        "attention before they become an outage."
    ),
    "html-to-pdf": (
        "Turn trusted HTML into a portable PDF artifact, with a signed receipt for every "
        "completed conversion."
    ),
    "world-time": (
        "Get current, location-aware time at call time. The answer is live evidence, not "
        "a stale bundled snapshot."
    ),
    "source-watch": (
        "Track a source for material changes and return evidence your agent can inspect "
        "before it acts."
    ),
}


def page_for_star(name: str, *, request: Request | None = None) -> Page:
    rec = CATALOG.resolve(name)
    if rec is None:
        raise NotFound(f"No resolve record for {name!r}")
    if rec.kind != "star":
        raise NotFound(f"{name!r} is a {rec.kind}, not a star")
    constellations = tuple(
        constellation
        for constellation in CATALOG.all()
        if constellation.name in rec.constellation_memberships
    )
    related = tuple(
        r for r in CATALOG.public_records() if r.kind == "star" and r.name != rec.name
    )[:3]
    layout = {}
    if request is not None:
        from pages._context import context

        layout = context(request)
    return Page(
        "star_detail.html",
        "content",
        page_block_name="content",
        rec=rec,
        oracle=oracle_for(rec),
        console_href=console_href_for(rec),
        publisher_note=PUBLISHER_DIRECT_NOTE,
        intro=_INTRO.get(
            rec.short_name, rec.description or "A callable capability in the public Orrery."
        ),
        constellations=constellations,
        related=related,
        page_title=f"{rec.name} — Orrery",
        footer_note="Star field guide",
        footer_meta="understand → call → verify",
        **layout,
    )
