"""Ping a publisher listing URL and land it in ``new/`` (ADR 0012)."""

from __future__ import annotations

import json
from collections.abc import Callable
from urllib.parse import urlparse

from catalog.models import ResolveRecord

from .fetch import fetch_and_cap
from .records import listing_to_record
from .schema import ListingError, assert_proof_of_control, parse_listing
from .store import ListingStore, persist_listing, require_listing_store, upsert_listing


def ping_listing(
    url: str,
    *,
    fetch: Callable[[str], bytes] | None = None,
    require_proof: bool = True,
    store: ListingStore | None = None,
) -> ResolveRecord:
    """Fetch, validate, persist, and upsert a newcomer catalog row."""
    if not isinstance(url, str) or not url.strip():
        raise ListingError("url_required", "url is required")
    cleaned = url.strip()
    if urlparse(cleaned).scheme != "https":
        raise ListingError("https_only", "listing URL must be https")
    target = require_listing_store(store)
    raw = fetch_and_cap(cleaned, fetch=fetch)
    doc = parse_listing(raw, listing_url=cleaned)
    if require_proof:
        assert_proof_of_control(cleaned, doc.endpoint)
    listing_json = json.loads(raw.decode("utf-8"))
    if not isinstance(listing_json, dict):
        raise ListingError("invalid_listing", "listing must be a JSON object")
    record = listing_to_record(doc)
    persist_listing(record, listing_json, store=target)
    return upsert_listing(record)
