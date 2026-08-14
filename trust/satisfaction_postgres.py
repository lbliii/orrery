"""Postgres adapter for envelope-gated satisfaction ratings (#459)."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol

from trust.satisfaction import (
    SatisfactionAggregate,
    SatisfactionRecord,
    SatisfactionStoreUnavailable,
)


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


class PostgresSatisfactionStore:
    """Durable ``SatisfactionStore`` keyed by ``(content_digest, authority_id)``."""

    table_sql = """
    CREATE TABLE IF NOT EXISTS satisfaction_ratings (
        content_digest TEXT NOT NULL,
        authority_id TEXT NOT NULL,
        authority_kind TEXT NOT NULL
            CHECK (authority_kind IN ('envelope', 'call_attempt')),
        star_name TEXT NOT NULL,
        verdict TEXT NOT NULL
            CHECK (verdict IN ('useful', 'stale', 'broken', 'wrong-price')),
        note TEXT,
        caller_namespace TEXT,
        created_at TIMESTAMPTZ NOT NULL,
        PRIMARY KEY (content_digest, authority_id)
    )
    """

    index_sql = """
    CREATE INDEX IF NOT EXISTS satisfaction_ratings_star_digest_idx
        ON satisfaction_ratings (star_name, content_digest)
    """

    _row_fields = (
        "content_digest, authority_id, authority_kind, star_name, verdict, "
        "note, caller_namespace, created_at"
    )

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
                raise SatisfactionStoreUnavailable(
                    "DATABASE_URL is required for durable satisfaction"
                )
            self._database_url = url
            self._connection_factory = self._connect
        self._initialized = False

    def _connect(self) -> Connection:
        import psycopg

        return psycopg.connect(self._database_url)

    def initialize(self) -> None:
        """Create the ratings table and aggregate index."""
        self._write(self.table_sql, ())
        self._write(self.index_sql, ())
        self._initialized = True

    def _ensure(self) -> None:
        if not self._initialized:
            self.initialize()

    def put(self, record: SatisfactionRecord) -> SatisfactionRecord:
        self._ensure()
        authority_id, authority_kind = _authority(record)
        self._write(
            f"""INSERT INTO satisfaction_ratings ({self._row_fields})
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (content_digest, authority_id) DO UPDATE SET
                 authority_kind = EXCLUDED.authority_kind,
                 star_name = EXCLUDED.star_name,
                 verdict = EXCLUDED.verdict,
                 note = EXCLUDED.note,
                 caller_namespace = EXCLUDED.caller_namespace,
                 created_at = EXCLUDED.created_at""",
            (
                record.content_digest,
                authority_id,
                authority_kind,
                record.star_name,
                record.verdict,
                record.note,
                record.caller_namespace,
                record.created_at,
            ),
        )
        return record

    def get_for_receipt(
        self,
        *,
        content_digest: str,
        envelope_id: str | None,
        call_attempt_id: str | None,
    ) -> SatisfactionRecord | None:
        authority = envelope_id or call_attempt_id
        if not authority:
            return None
        self._ensure()
        row = self._read(
            f"""SELECT {self._row_fields} FROM satisfaction_ratings
               WHERE content_digest = %s AND authority_id = %s""",
            (content_digest, authority),
        )
        return _record_from_row(row) if row is not None else None

    def aggregate(
        self,
        *,
        star_name: str,
        content_digest: str,
        since: datetime | None = None,
    ) -> SatisfactionAggregate:
        self._ensure()
        rows = self._read_all(
            """SELECT verdict, COUNT(*) FROM satisfaction_ratings
               WHERE star_name = %s AND content_digest = %s
                 AND (%s IS NULL OR created_at >= %s)
               GROUP BY verdict ORDER BY verdict""",
            (star_name, content_digest, since, since),
        )
        counts = {str(verdict): int(total) for verdict, total in rows}
        return SatisfactionAggregate(
            star_name=star_name,
            content_digest=content_digest,
            counts=counts,
            total=sum(counts.values()),
        )

    def records_for(self, star_name: str) -> tuple[SatisfactionRecord, ...]:
        self._ensure()
        rows = self._read_all(
            f"""SELECT {self._row_fields} FROM satisfaction_ratings
               WHERE star_name = %s""",
            (star_name,),
        )
        return tuple(_record_from_row(row) for row in rows)

    def _write(self, query: str, params: tuple[Any, ...]) -> None:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(query, params)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def _read(self, query: str, params: tuple[Any, ...]) -> Any:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(query, params)
            return cursor.fetchone()
        finally:
            cursor.close()
            connection.close()

    def _read_all(self, query: str, params: tuple[Any, ...]) -> list[Any]:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(query, params)
            return list(cursor.fetchall())
        finally:
            cursor.close()
            connection.close()


def _authority(record: SatisfactionRecord) -> tuple[str, str]:
    if record.envelope_id:
        return record.envelope_id, "envelope"
    if record.call_attempt_id:
        return record.call_attempt_id, "call_attempt"
    raise ValueError("satisfaction row requires envelope_id or call_attempt_id")


def _record_from_row(row: tuple[Any, ...]) -> SatisfactionRecord:
    content_digest, authority_id, authority_kind, star_name, verdict, note, namespace, created = (
        row
    )
    kind = str(authority_kind)
    return SatisfactionRecord(
        star_name=str(star_name),
        content_digest=str(content_digest),
        verdict=str(verdict),
        created_at=_created_at_iso(created),
        envelope_id=str(authority_id) if kind == "envelope" else None,
        call_attempt_id=str(authority_id) if kind == "call_attempt" else None,
        note=None if note is None else str(note),
        caller_namespace=None if namespace is None else str(namespace),
    )


def _created_at_iso(value: datetime | str) -> str:
    if isinstance(value, datetime):
        stamp = value.astimezone(UTC).replace(microsecond=0).isoformat()
        return stamp.replace("+00:00", "Z")
    return str(value)
