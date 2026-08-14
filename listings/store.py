"""In-process listing store + fixture allowlist (ADR 0012)."""

from __future__ import annotations

import json
from pathlib import Path

from catalog.models import ResolveRecord
from catalog.store import CATALOG, replace_catalog

from .records import listing_to_record
from .schema import ListingError, parse_listing

PACKAGE_DIR = Path(__file__).resolve().parent
ALLOWLIST_PATH = PACKAGE_DIR / "allowlist.json"

_LISTINGS: dict[str, ResolveRecord] = {}


def listing_records() -> tuple[ResolveRecord, ...]:
    """Current newcomer (and promoted) listing rows."""
    return tuple(_LISTINGS.values())


def reset_listing_store() -> None:
    """Drop in-process listings (tests)."""
    _LISTINGS.clear()


def upsert_listing(record: ResolveRecord, *, merge_catalog: bool = True) -> ResolveRecord:
    """Remember a listing row and optionally merge it into ``CATALOG``."""
    _LISTINGS[record.name] = record
    if merge_catalog:
        kept = tuple(r for r in CATALOG.all() if r.name != record.name)
        replace_catalog((*kept, record))
    return record


def load_allowlist_fixtures(*, path: Path | None = None) -> tuple[ResolveRecord, ...]:
    """Load ``kind: fixture`` allowlist entries (no network)."""
    source = path or ALLOWLIST_PATH
    if not source.is_file():
        return ()
    data = json.loads(source.read_text())
    rows = data.get("listings") or []
    loaded: list[ResolveRecord] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("kind") != "fixture":
            continue
        rel = str(row.get("path") or "")
        fixture = (source.parent / rel).resolve()
        if not fixture.is_file() or PACKAGE_DIR not in fixture.parents:
            raise ListingError("invalid_listing", f"fixture missing: {rel}")
        raw = fixture.read_bytes()
        doc = parse_listing(raw, listing_url=f"fixture://{rel}")
        record = listing_to_record(doc)
        upsert_listing(record, merge_catalog=False)
        loaded.append(record)
    return tuple(loaded)
