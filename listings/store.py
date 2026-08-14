"""In-process listing catalog plus durable row store (ADR 0012 / #458)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from catalog.models import ResolveRecord
from catalog.store import CATALOG, replace_catalog

from .records import listing_to_record
from .schema import ListingError, parse_listing

PACKAGE_DIR = Path(__file__).resolve().parent
ALLOWLIST_PATH = PACKAGE_DIR / "allowlist.json"

_LISTINGS: dict[str, ResolveRecord] = {}
_injected: ListingStore | None = None
_env_store: ListingStore | None = None


class ListingStoreConfigError(RuntimeError):
    """Postgres listing store constructed without ``DATABASE_URL``."""


@dataclass(frozen=True, slots=True)
class ListingRow:
    """One durable listing_rows tuple (PK ``listing_url``)."""

    listing_url: str
    listing_json: dict[str, Any]
    content_digest: str
    live_name: str
    claimed_name: str | None
    endpoint: str
    index_tier: str
    promoted_to: str | None
    quiet: bool
    last_fetch_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class ListingStore(Protocol):
    """Durable listing rows. Tests inject ``InMemoryListingStore``."""

    def upsert(
        self,
        *,
        listing_url: str,
        listing_json: dict[str, Any],
        content_digest: str,
        live_name: str,
        claimed_name: str | None,
        endpoint: str,
        index_tier: str,
        promoted_to: str | None = None,
        quiet: bool = False,
        last_error: str | None = None,
    ) -> ListingRow: ...

    def get(self, listing_url: str) -> ListingRow | None: ...

    def load_all(self) -> tuple[ListingRow, ...]: ...

    def list_urls(self) -> tuple[str, ...]: ...


def digest_overlay(
    existing: ListingRow | None,
    *,
    content_digest: str,
    quiet: bool,
    promoted_to: str | None,
) -> tuple[bool, str | None]:
    """New live digest clears ``quiet`` and ``promoted_to`` (durable-store freeze)."""
    if existing is not None and existing.content_digest != content_digest:
        return False, None
    return quiet, promoted_to


class InMemoryListingStore:
    """Process-local rows. Pass a shared ``rows`` dict to simulate restart."""

    def __init__(self, rows: dict[str, ListingRow] | None = None) -> None:
        self._rows = rows if rows is not None else {}

    def upsert(
        self,
        *,
        listing_url: str,
        listing_json: dict[str, Any],
        content_digest: str,
        live_name: str,
        claimed_name: str | None,
        endpoint: str,
        index_tier: str,
        promoted_to: str | None = None,
        quiet: bool = False,
        last_error: str | None = None,
    ) -> ListingRow:
        now = datetime.now(UTC)
        existing = self._rows.get(listing_url)
        quiet, promoted_to = digest_overlay(
            existing,
            content_digest=content_digest,
            quiet=quiet,
            promoted_to=promoted_to,
        )
        row = ListingRow(
            listing_url=listing_url,
            listing_json=dict(listing_json),
            content_digest=content_digest,
            live_name=live_name,
            claimed_name=claimed_name,
            endpoint=endpoint,
            index_tier=index_tier,
            promoted_to=promoted_to,
            quiet=quiet,
            last_fetch_at=now,
            last_error=last_error,
            created_at=existing.created_at if existing is not None else now,
            updated_at=now,
        )
        self._rows[listing_url] = row
        return row

    def get(self, listing_url: str) -> ListingRow | None:
        return self._rows.get(listing_url)

    def load_all(self) -> tuple[ListingRow, ...]:
        return tuple(self._rows[key] for key in sorted(self._rows))

    def list_urls(self) -> tuple[str, ...]:
        return tuple(sorted(self._rows))


def configure_listing_store(store: ListingStore | None) -> None:
    """Inject a store for tests, or ``None`` to restore the host factory."""
    global _injected, _env_store
    _injected = store
    if store is None:
        _env_store = None


def listing_store_from_env() -> ListingStore:
    """Postgres when ``DATABASE_URL`` is set; otherwise an empty in-memory stub."""
    global _env_store
    if _injected is not None:
        return _injected
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        return InMemoryListingStore()
    if _env_store is None:
        from .postgres import PostgresListingStore

        _env_store = PostgresListingStore(database_url=url)
    return _env_store


def require_listing_store(store: ListingStore | None = None) -> ListingStore:
    """Ping path: injected store, or Postgres, or parseable ``store_unavailable``."""
    if store is not None:
        return store
    if _injected is not None:
        return _injected
    if not os.environ.get("DATABASE_URL", "").strip():
        raise ListingError(
            "store_unavailable",
            "listing store requires DATABASE_URL",
        )
    return listing_store_from_env()


def project_listing_row(row: ListingRow) -> ResolveRecord:
    """Rebuild a catalog row from stored listing JSON plus durable overlays."""
    raw = json.dumps(row.listing_json).encode()
    record = listing_to_record(parse_listing(raw, listing_url=row.listing_url))
    return replace(
        record,
        name=row.live_name,
        endpoint=row.endpoint,
        content_digest=row.content_digest,
        index_tier=row.index_tier,
        claimed_name=row.claimed_name,
        listing_url=row.listing_url,
        promoted_to=row.promoted_to,
    )


def boot_durable_listings(
    *,
    store: ListingStore | None = None,
    merge_catalog: bool = True,
) -> tuple[ResolveRecord, ...]:
    """Project durable rows into the in-process catalog (fixtures load separately)."""
    target = store if store is not None else listing_store_from_env()
    loaded: list[ResolveRecord] = []
    for row in target.load_all():
        record = project_listing_row(row)
        upsert_listing(record, merge_catalog=merge_catalog)
        loaded.append(record)
    return tuple(loaded)


def list_urls(*, store: ListingStore | None = None) -> tuple[str, ...]:
    """Job-facing: known listing URLs only (never discovers hosts)."""
    target = store if store is not None else listing_store_from_env()
    return target.list_urls()


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


def persist_listing(
    record: ResolveRecord,
    listing_json: dict[str, Any],
    *,
    store: ListingStore | None = None,
    last_error: str | None = None,
) -> ListingRow:
    """Write a durable row for a successful ping (upsert by ``listing_url``)."""
    url = record.listing_url
    if not url:
        raise ListingError("url_required", "listing_url is required to persist")
    target = require_listing_store(store)
    return target.upsert(
        listing_url=url,
        listing_json=listing_json,
        content_digest=record.content_digest,
        live_name=record.name,
        claimed_name=record.claimed_name,
        endpoint=record.endpoint,
        index_tier=record.index_tier or "newcomer",
        promoted_to=record.promoted_to,
        last_error=last_error,
    )


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
