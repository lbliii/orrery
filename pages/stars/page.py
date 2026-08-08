"""Star detail — one resolvable skill: manifest, price, last Envelope.

Resolves ``?name=`` against the catalog (defaults to the demo star). Unknown or
non-star names 404 instead of silently falling back, so live resolve and the
detail page share one contract. Demo stars invoke tools server-side so the
receipt is a real signed Envelope (html-to-pdf plumbing #25-#27; world-time
reactive spike #37).
"""

from __future__ import annotations

import json

from chirp import NotFound, Page, Request

from catalog import CATALOG
from dogfood import (
    SMOKE_HTML,
    WORLD_TIME_CLONE_WARNING,
    signed_convert_receipt,
    signed_world_time_receipt,
)

_DEFAULT = "orrery/html-to-pdf"
_PDF_STAR = "orrery/html-to-pdf"
_WORLD_TIME_STAR = "orrery/world-time"


def get(request: Request) -> Page:
    raw = (request.query.get("name") or "").strip()
    name = raw or _DEFAULT
    rec = CATALOG.resolve(name)
    if rec is None:
        raise NotFound(f"No resolve record for {name!r}")
    if rec.kind != "star":
        raise NotFound(f"{name!r} is a {rec.kind}, not a star — open {rec.href}")

    envelope: dict | None = None
    verified = False
    if rec.name == _PDF_STAR:
        envelope, verified = signed_convert_receipt(SMOKE_HTML)
    elif rec.name == _WORLD_TIME_STAR:
        envelope, verified = signed_world_time_receipt()

    envelope_json = (
        json.dumps(
            {
                "skill": envelope["skill"],
                "version": envelope["version"],
                "tool": envelope["tool"],
                "input_digest": envelope["input_digest"],
                "nonce": envelope["nonce"],
                "key_id": envelope["key_id"],
                "alg": envelope["alg"],
                "payment_id": envelope.get("payment_id"),
                "signature": envelope["signature"],
            },
            indent=2,
        )
        if envelope is not None
        else None
    )

    return Page(
        "stars/page.html",
        "content",
        page_block_name="content",
        rec=rec,
        page_title=f"{rec.name} — Orrery",
        footer_note="Star detail",
        footer_meta="pay → result → receipt",
        resolved_via=name,
        envelope=envelope,
        envelope_json=envelope_json,
        verified=verified,
        is_reactive=rec.name == _WORLD_TIME_STAR,
        clone_warning=WORLD_TIME_CLONE_WARNING if rec.name == _WORLD_TIME_STAR else None,
    )
