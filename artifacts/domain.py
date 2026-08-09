"""Artifact metadata persisted independently from artifact bytes."""

from __future__ import annotations

import json
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol


class ArtifactState(StrEnum):
    """The only permitted artifact lifecycle states."""

    PENDING_UPLOAD = "pending_upload"
    AVAILABLE = "available"
    DELETING = "deleting"
    DELETED = "deleted"


@dataclass(frozen=True)
class ArtifactPolicy:
    """Access and retention policy stored with an artifact."""

    access: str = "private"
    owner_id: str | None = None
    namespace: str | None = None
    retention_class: str = "ephemeral"

    def as_dict(self) -> dict[str, str | None]:
        return {
            "access": self.access,
            "owner_id": self.owner_id,
            "namespace": self.namespace,
            "retention_class": self.retention_class,
        }


@dataclass(frozen=True)
class ArtifactRecord:
    """Durable metadata for an immutable uploaded artifact."""

    artifact_id: str
    storage_key: str
    sha256: str
    byte_length: int
    content_type: str
    filename: str
    expires_at: datetime
    policy: ArtifactPolicy
    state: ArtifactState = ArtifactState.PENDING_UPLOAD


def artifact_storage_key(artifact_id: str) -> str:
    """Return a non-guessable, provider-neutral key for an artifact."""
    return f"artifacts/{artifact_id}"


def new_artifact_id() -> str:
    """Generate an opaque URL-safe ID; callers never derive it from content."""
    return secrets.token_urlsafe(24)


class Cursor(Protocol):
    def execute(self, query: str, params: tuple[Any, ...] = ()) -> Any: ...

    def fetchone(self) -> Any: ...

    def close(self) -> None: ...


class Connection(Protocol):
    def cursor(self) -> Cursor: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...


class PostgresArtifactRepository:
    """Postgres persistence for artifact metadata, never for artifact bytes."""

    schema_sql = """
    CREATE TABLE IF NOT EXISTS artifacts (
        artifact_id TEXT PRIMARY KEY,
        storage_key TEXT NOT NULL UNIQUE,
        sha256 TEXT NOT NULL,
        byte_length BIGINT NOT NULL CHECK (byte_length >= 0),
        content_type TEXT NOT NULL,
        filename TEXT NOT NULL,
        expires_at TIMESTAMPTZ NOT NULL,
        policy JSONB NOT NULL,
        state TEXT NOT NULL CHECK (state IN ('pending_upload', 'available', 'deleting', 'deleted')),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS artifacts_expiry_idx ON artifacts (expires_at)
        WHERE state IN ('pending_upload', 'available', 'deleting');
    """

    def __init__(self, connection_factory: Callable[[], Connection]) -> None:
        self._connection_factory = connection_factory

    def initialize(self) -> None:
        """Create the metadata table and expiry index."""
        self._write(self.schema_sql, ())

    def create_pending(self, record: ArtifactRecord) -> ArtifactRecord:
        """Persist upload intent before bytes are sent to object storage."""
        if record.state is not ArtifactState.PENDING_UPLOAD:
            raise ValueError("new artifacts must begin in pending_upload")
        self._write(
            """INSERT INTO artifacts
               (artifact_id, storage_key, sha256, byte_length, content_type, filename,
                expires_at, policy, state)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)""",
            (
                record.artifact_id,
                record.storage_key,
                record.sha256,
                record.byte_length,
                record.content_type,
                record.filename,
                record.expires_at,
                json.dumps(record.policy.as_dict()),
                record.state.value,
            ),
        )
        return record

    def transition(
        self, artifact_id: str, *, from_state: ArtifactState, to_state: ArtifactState
    ) -> bool:
        """Atomically transition a record; false means it was not in expected state."""
        permitted = {
            (ArtifactState.PENDING_UPLOAD, ArtifactState.AVAILABLE),
            (ArtifactState.PENDING_UPLOAD, ArtifactState.DELETING),
            (ArtifactState.AVAILABLE, ArtifactState.DELETING),
            (ArtifactState.DELETING, ArtifactState.DELETED),
        }
        if (from_state, to_state) not in permitted:
            raise ValueError(f"invalid artifact transition: {from_state} -> {to_state}")
        row = self._write(
            """UPDATE artifacts SET state = %s, updated_at = NOW()
               WHERE artifact_id = %s AND state = %s
               RETURNING artifact_id""",
            (to_state.value, artifact_id, from_state.value),
            fetch_one=True,
        )
        return row is not None

    def mark_available(self, artifact_id: str) -> bool:
        """Mark an object whose upload completed and was checksum-verified."""
        return self.transition(
            artifact_id,
            from_state=ArtifactState.PENDING_UPLOAD,
            to_state=ArtifactState.AVAILABLE,
        )

    def mark_deleting(self, artifact_id: str, *, state: ArtifactState) -> bool:
        """Claim a pending or available artifact for deletion."""
        if state not in {ArtifactState.PENDING_UPLOAD, ArtifactState.AVAILABLE}:
            raise ValueError("only pending_upload or available artifacts can be deleted")
        return self.transition(artifact_id, from_state=state, to_state=ArtifactState.DELETING)

    def mark_deleted(self, artifact_id: str) -> bool:
        """Record deletion after object storage has removed the bytes."""
        return self.transition(
            artifact_id,
            from_state=ArtifactState.DELETING,
            to_state=ArtifactState.DELETED,
        )

    def get(self, artifact_id: str) -> ArtifactRecord | None:
        """Load metadata only; delivery code gets bytes from object storage."""
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """SELECT artifact_id, storage_key, sha256, byte_length, content_type,
                          filename, expires_at, policy, state
                   FROM artifacts WHERE artifact_id = %s""",
                (artifact_id,),
            )
            row = cursor.fetchone()
            return self._record_from_row(row) if row is not None else None
        finally:
            cursor.close()
            connection.close()

    def _write(self, query: str, params: tuple[Any, ...], *, fetch_one: bool = False) -> Any:
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

    @staticmethod
    def _record_from_row(row: tuple[Any, ...]) -> ArtifactRecord:
        policy = row[7]
        if isinstance(policy, str):
            policy = json.loads(policy)
        return ArtifactRecord(
            artifact_id=row[0], storage_key=row[1], sha256=row[2], byte_length=row[3],
            content_type=row[4], filename=row[5], expires_at=row[6],
            policy=ArtifactPolicy(**policy), state=ArtifactState(row[8]),
        )


def expires_at_after(seconds: int) -> datetime:
    """Return a UTC expiry suitable for a Postgres TIMESTAMPTZ column."""
    return datetime.now(UTC).replace(microsecond=0) + timedelta(seconds=seconds)
