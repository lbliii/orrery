"""Star detail — one resolvable skill: manifest, price, last Envelope.

Resolves ``?name=`` against the catalog (defaults to the demo star). Unknown or
non-star names 404 instead of silently falling back, so live resolve and the
detail page share one contract. Backs GitHub issues #25 / #26.
"""

from __future__ import annotations

from chirp import NotFound, Page, Request

from catalog import CATALOG

_DEFAULT = "orrery/html-to-pdf"


def get(request: Request) -> Page:
    raw = (request.query.get("name") or "").strip()
    name = raw or _DEFAULT
    rec = CATALOG.resolve(name)
    if rec is None:
        raise NotFound(f"No resolve record for {name!r}")
    if rec.kind != "star":
        raise NotFound(f"{name!r} is a {rec.kind}, not a star — open {rec.href}")
    return Page(
        "stars/page.html",
        "content",
        page_block_name="content",
        rec=rec,
        page_title=f"{rec.name} — Orrery",
        footer_note="Star detail",
        footer_meta="pay → result → receipt",
        resolved_via=name,
    )
