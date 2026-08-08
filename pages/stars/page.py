"""Star detail — one resolvable skill: manifest, price, last Envelope.

Resolves ``?name=`` against the catalog (defaults to the demo star). Unknown or
non-star names 404 instead of silently falling back, so live resolve and the
detail page share one contract. For the demo star, invokes the html-to-pdf
``convert`` tool server-side so the receipt is a real signed Envelope
(issues #25 / #26 / #27).
"""

from __future__ import annotations

import json

from chirp import NotFound, Page, Request

from catalog import CATALOG
from dogfood import SMOKE_HTML, signed_convert_receipt

_DEFAULT = "orrery/html-to-pdf"


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
    if rec.name == _DEFAULT:
        envelope, verified = signed_convert_receipt(SMOKE_HTML)

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
    )
