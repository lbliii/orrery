"""Ping a publisher listing URL and land it in ``new/`` (ADR 0012)."""

from __future__ import annotations

from collections.abc import Callable

from catalog.models import ResolveRecord

from .fetch import fetch_and_cap
from .records import listing_to_record
from .schema import ListingError, assert_proof_of_control, parse_listing
from .store import upsert_listing


def ping_listing(
    url: str,
    *,
    fetch: Callable[[str], bytes] | None = None,
    require_proof: bool = True,
) -> ResolveRecord:
    """Fetch, validate, and upsert a newcomer catalog row."""
    if not isinstance(url, str) or not url.strip():
        raise ListingError("url_required", "url is required")
    raw = fetch_and_cap(url.strip(), fetch=fetch)
    doc = parse_listing(raw, listing_url=url.strip())
    if require_proof:
        assert_proof_of_control(url.strip(), doc.endpoint)
    return upsert_listing(listing_to_record(doc))
