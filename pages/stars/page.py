"""Star detail — one resolvable skill: manifest, price, last Envelope.

Resolves ``?name=`` against the catalog (defaults to the demo star). Unknown or
non-star names 404 instead of silently falling back, so live resolve and the
detail page share one contract. Demo stars invoke tools server-side so the
receipt is a real signed Envelope (html-to-pdf plumbing #25-#27; world-time
reactive spike #37; source-watch evidence #51).
"""

from __future__ import annotations

import json

from chirp import NotFound, Page, Request

from catalog import CATALOG
from catalog.console_links import PUBLISHER_DIRECT_NOTE, console_href_for
from commerce import charge_on_verify, refund_on_forge
from dogfood import (
    SMOKE_HTML,
    WORLD_TIME_CLONE_WARNING,
    signed_convert_receipt,
    signed_source_watch_receipt,
    signed_world_time_receipt,
)
from trust.oracle import oracle_for

_DEFAULT = "orrery/html-to-pdf"
_PDF_STAR = "orrery/html-to-pdf"
_WORLD_TIME_STAR = "orrery/world-time"
_SOURCE_WATCH_STAR = "orrery/source-watch"


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
    elif rec.name == _SOURCE_WATCH_STAR:
        envelope, verified = signed_source_watch_receipt()

    if envelope is not None:
        # Star-page verify path: same loud stubs as ``/api/envelope/verify``.
        payment_id = envelope.get("payment_id")
        price = envelope.get("price_per_call") or rec.price_per_call
        if verified:
            charge_on_verify(
                payment_id=str(payment_id) if payment_id else None,
                price_per_call=str(price) if price else None,
                skill=str(envelope.get("skill")),
                nonce=str(envelope.get("nonce")),
                reason="star_page_verified",
            )
        else:
            refund_on_forge(
                payment_id=str(payment_id) if payment_id else None,
                price_per_call=str(price) if price else None,
                skill=str(envelope.get("skill")),
                nonce=str(envelope.get("nonce")),
                reason="star_page_forge_or_fail",
            )

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
                "price_per_call": envelope.get("price_per_call") or rec.price_per_call,
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
        oracle=oracle_for(rec),
        console_href=console_href_for(rec),
        publisher_note=PUBLISHER_DIRECT_NOTE,
        page_title=f"{rec.name} — Orrery",
        footer_note="Star detail",
        footer_meta="call → verify → receipt",
        resolved_via=name,
        envelope=envelope,
        envelope_json=envelope_json,
        verified=verified,
        is_reactive=rec.name == _WORLD_TIME_STAR,
        clone_warning=WORLD_TIME_CLONE_WARNING if rec.name == _WORLD_TIME_STAR else None,
    )
