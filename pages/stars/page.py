"""Star detail — one resolvable skill: manifest, price, last Envelope.

Resolves ``?name=`` against the catalog (defaults to the demo star) and renders
the call/verify/receipt story from ``design/star.html``. Backs GitHub epic #5
(Call / Envelope).
"""

from __future__ import annotations

from chirp import Page, Request

from catalog import CATALOG

_DEFAULT = "orrery/html-to-pdf"


def get(request: Request) -> Page:
    name = (request.query.get("name") or _DEFAULT).strip()
    rec = CATALOG.resolve(name)
    if rec is None or rec.kind != "star":
        rec = CATALOG.get(_DEFAULT)
    return Page(
        "stars/page.html",
        "content",
        page_block_name="content",
        rec=rec,
        page_title=f"{rec.name} — Orrery",
        footer_note="Star detail",
        footer_meta="pay → result → receipt",
    )
