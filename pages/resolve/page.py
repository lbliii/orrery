"""Resolve — the "Skill DNS" console.

Lists the public resolver zone from the catalog and, when a lookup ``?q=`` is
present, resolves it to a single record (server-side mirror of the client
resolver in ``static/motion.js``). Backs GitHub epic #4 (Resolve).
"""

from __future__ import annotations

from chirp import Page, Request

from catalog import CATALOG


def get(request: Request) -> Page:
    q = (request.query.get("q") or "").strip()
    matched = CATALOG.resolve(q) if q else None
    return Page(
        "resolve/page.html",
        "content",
        page_block_name="content",
        page_title="Resolve — Orrery",
        footer_note="Resolver console",
        records=CATALOG.public_records(),
        q=q,
        matched=matched,
        matched_name=matched.name if matched else "",
    )
