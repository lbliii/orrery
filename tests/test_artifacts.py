"""Tests for durable artifact metadata and object storage ports."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from artifacts import (
    ArtifactPolicy,
    ArtifactRecord,
    ArtifactState,
    InMemoryObjectStorage,
    PostgresArtifactRepository,
    S3ObjectStorage,
    artifact_storage_key,
)


def test_fake_object_storage_round_trip_and_delete() -> None:
    storage = InMemoryObjectStorage()
    storage.put(key="artifacts/opaque", data=b"%PDF-1.4", content_type="application/pdf")

    assert storage.get(key="artifacts/opaque") == b"%PDF-1.4"
    storage.delete(key="artifacts/opaque")
    assert storage.get(key="artifacts/opaque") is None


def test_s3_adapter_uses_bucket_and_preserves_bytes() -> None:
    client = _FakeS3Client()
    storage = S3ObjectStorage(client, bucket="orrery-artifacts")
    storage.put(key="artifacts/a", data=b"hello", content_type="text/plain")

    assert storage.get(key="artifacts/a") == b"hello"
    assert client.puts == [("orrery-artifacts", "artifacts/a", b"hello", "text/plain")]
    storage.delete(key="artifacts/a")
    assert storage.get(key="artifacts/a") is None


def test_artifact_record_has_required_durable_metadata() -> None:
    record = ArtifactRecord(
        artifact_id="opaque-id", storage_key=artifact_storage_key("opaque-id"),
        sha256="sha256:abc", byte_length=42, content_type="text/csv", filename="report.csv",
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
        policy=ArtifactPolicy(access="receipt-holder", owner_id="run-123"),
    )

    assert record.state is ArtifactState.PENDING_UPLOAD
    assert record.storage_key == "artifacts/opaque-id"
    assert record.policy.as_dict()["access"] == "receipt-holder"


def test_postgres_repository_inserts_pending_and_uses_guarded_transition() -> None:
    connection = _FakeConnection(return_row=("opaque-id",))
    repository = PostgresArtifactRepository(lambda: connection)
    record = ArtifactRecord(
        artifact_id="opaque-id", storage_key="artifacts/opaque-id", sha256="sha256:abc",
        byte_length=1, content_type="text/plain", filename="a.txt",
        expires_at=datetime.now(UTC), policy=ArtifactPolicy(),
    )

    assert repository.create_pending(record) == record
    assert repository.transition(
        "opaque-id", from_state=ArtifactState.PENDING_UPLOAD, to_state=ArtifactState.AVAILABLE
    ) is True
    assert "INSERT INTO artifacts" in connection.cursor_instance.calls[0][0]
    transition_query, params = connection.cursor_instance.calls[1]
    assert "WHERE artifact_id = %s AND state = %s" in transition_query
    assert params == ("available", "opaque-id", "pending_upload")


def test_postgres_repository_rejects_invalid_initial_state() -> None:
    repository = PostgresArtifactRepository(lambda: _FakeConnection())
    record = ArtifactRecord(
        artifact_id="id", storage_key="artifacts/id", sha256="sha256:abc", byte_length=0,
        content_type="application/octet-stream", filename="empty", expires_at=datetime.now(UTC),
        policy=ArtifactPolicy(), state=ArtifactState.AVAILABLE,
    )

    with pytest.raises(ValueError, match="pending_upload"):
        repository.create_pending(record)


def test_postgres_repository_rejects_invalid_lifecycle_transition() -> None:
    repository = PostgresArtifactRepository(lambda: _FakeConnection())

    with pytest.raises(ValueError, match="invalid artifact transition"):
        repository.transition(
            "id", from_state=ArtifactState.AVAILABLE, to_state=ArtifactState.PENDING_UPLOAD
        )


class _Body:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data


class _NotFound(Exception):
    def __init__(self) -> None:
        self.response = {"Error": {"Code": "NoSuchKey"}}


class _FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.puts: list[tuple[str, str, bytes, str]] = []

    def put_object(self, **kwargs: object) -> None:
        bucket, key, body, content_type = (
            str(kwargs["Bucket"]),
            str(kwargs["Key"]),
            bytes(kwargs["Body"]),
            str(kwargs["ContentType"]),
        )
        self.objects[(bucket, key)] = body
        self.puts.append((bucket, key, body, content_type))

    def get_object(self, **kwargs: object) -> dict[str, _Body]:
        try:
            return {"Body": _Body(self.objects[(str(kwargs["Bucket"]), str(kwargs["Key"]))])}
        except KeyError as exc:
            raise _NotFound() from exc

    def delete_object(self, **kwargs: object) -> None:
        self.objects.pop((str(kwargs["Bucket"]), str(kwargs["Key"])), None)


class _FakeCursor:
    def __init__(self, return_row: tuple[str] | None) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.return_row = return_row

    def execute(self, query: str, params: tuple[object, ...] = ()) -> None:
        self.calls.append((query, params))

    def fetchone(self) -> tuple[str] | None:
        return self.return_row

    def close(self) -> None:
        pass


class _FakeConnection:
    def __init__(self, return_row: tuple[str] | None = None) -> None:
        self.cursor_instance = _FakeCursor(return_row)

    def cursor(self) -> _FakeCursor:
        return self.cursor_instance

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        pass
