"""Postgres adapter for ``listing_rows`` (artifacts.domain / #458)."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any, Protocol

from .store import ListingRow, ListingStoreConfigError, digest_overlay


class Cursor(Protocol):
    def execute(self, query: str, params: tuple[Any, ...] = ()) -> Any: ...

    def fetchone(self) -> Any: ...

    def fetchall(self) -> list[Any]: ...

    def close(self) -> None: ...


class Connection(Protocol):
    def cursor(self) -> Cursor: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...


class PostgresListingStore:
    """Durable ``listing_rows``. Fail-closed if constructed without ``DATABASE_URL``."""

    schema_sql = """
    CREATE TABLE IF NOT EXISTS listing_rows (
        listing_url TEXT PRIMARY KEY,
        listing_json JSONB NOT NULL,
        content_digest TEXT NOT NULL,
        live_name TEXT NOT NULL,
        claimed_name TEXT,
        endpoint TEXT NOT NULL,
        index_tier TEXT NOT NULL,
        promoted_to TEXT,
        quiet BOOLEAN NOT NULL DEFAULT FALSE,
        last_fetch_at TIMESTAMPTZ,
        last_error TEXT,
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL
    );
    """

    def __init__(
        self,
        connection_factory: Callable[[], Connection] | None = None,
        *,
        database_url: str | None = None,
    ) -> None:
        if connection_factory is not None:
            self._connection_factory = connection_factory
        else:
            url = (
                database_url if database_url is not None else os.environ.get("DATABASE_URL", "")
            ).strip()
            if not url:
                raise ListingStoreConfigError(
                    "DATABASE_URL is required for Postgres listing store"
                )
            self._database_url = url
            self._connection_factory = self._connect
        self._initialized = False

    def _connect(self) -> Connection:
        import psycopg

        return psycopg.connect(self._database_url)

    def initialize(self) -> None:
        """``CREATE TABLE IF NOT EXISTS`` on first use (artifact pattern)."""
        self._write(self.schema_sql, ())
        self._initialized = True

    def _ensure(self) -> None:
        if not self._initialized:
            self.initialize()

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
        self._ensure()
        existing = self.get(listing_url)
        quiet, promoted_to = digest_overlay(
            existing,
            content_digest=content_digest,
            quiet=quiet,
            promoted_to=promoted_to,
        )
        row = self._write(
            """INSERT INTO listing_rows (
                   listing_url, listing_json, content_digest, live_name, claimed_name,
                   endpoint, index_tier, promoted_to, quiet, last_fetch_at, last_error,
                   created_at, updated_at
               ) VALUES (
                   %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, NOW(), NOW()
               )
               ON CONFLICT (listing_url) DO UPDATE SET
                   listing_json = EXCLUDED.listing_json,
                   content_digest = EXCLUDED.content_digest,
                   live_name = EXCLUDED.live_name,
                   claimed_name = EXCLUDED.claimed_name,
                   endpoint = EXCLUDED.endpoint,
                   index_tier = EXCLUDED.index_tier,
                   promoted_to = EXCLUDED.promoted_to,
                   quiet = EXCLUDED.quiet,
                   last_fetch_at = EXCLUDED.last_fetch_at,
                   last_error = EXCLUDED.last_error,
                   updated_at = NOW()
               RETURNING listing_url, listing_json, content_digest, live_name,
                         claimed_name, endpoint, index_tier, promoted_to, quiet,
                         last_fetch_at, last_error, created_at, updated_at""",
            (
                listing_url,
                json.dumps(listing_json),
                content_digest,
                live_name,
                claimed_name,
                endpoint,
                index_tier,
                promoted_to,
                quiet,
                last_error,
            ),
            fetch_one=True,
        )
        return self._record_from_row(row)

    def get(self, listing_url: str) -> ListingRow | None:
        self._ensure()
        row = self._read(
            """SELECT listing_url, listing_json, content_digest, live_name,
                      claimed_name, endpoint, index_tier, promoted_to, quiet,
                      last_fetch_at, last_error, created_at, updated_at
               FROM listing_rows WHERE listing_url = %s""",
            (listing_url,),
        )
        return self._record_from_row(row) if row is not None else None

    def load_all(self) -> tuple[ListingRow, ...]:
        self._ensure()
        rows = self._read_all(
            """SELECT listing_url, listing_json, content_digest, live_name,
                      claimed_name, endpoint, index_tier, promoted_to, quiet,
                      last_fetch_at, last_error, created_at, updated_at
               FROM listing_rows ORDER BY listing_url"""
        )
        return tuple(self._record_from_row(row) for row in rows)

    def list_urls(self) -> tuple[str, ...]:
        self._ensure()
        rows = self._read_all("SELECT listing_url FROM listing_rows ORDER BY listing_url")
        return tuple(row[0] for row in rows)

    def _write(
        self, query: str, params: tuple[Any, ...], *, fetch_one: bool = False
    ) -> Any:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(query, params)
            row = cursor.fetchone() if fetch_one else None
            connection.commit()
            return row
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def _read(self, query: str, params: tuple[Any, ...] = ()) -> Any:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(query, params)
            return cursor.fetchone()
        finally:
            cursor.close()
            connection.close()

    def _read_all(self, query: str, params: tuple[Any, ...] = ()) -> list[Any]:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(query, params)
            return list(cursor.fetchall())
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def _record_from_row(row: tuple[Any, ...]) -> ListingRow:
        listing_json = row[1]
        if isinstance(listing_json, str):
            listing_json = json.loads(listing_json)
        return ListingRow(
            listing_url=row[0],
            listing_json=listing_json,
            content_digest=row[2],
            live_name=row[3],
            claimed_name=row[4],
            endpoint=row[5],
            index_tier=row[6],
            promoted_to=row[7],
            quiet=bool(row[8]),
            last_fetch_at=row[9],
            last_error=row[10],
            created_at=row[11],
            updated_at=row[12],
        )
