"""Focused tests for single-object artifact capabilities and finalization."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from artifacts import (
    ArtifactCapabilityService,
    ArtifactCapabilitySettings,
    ArtifactPolicy,
    ArtifactRecord,
    ArtifactState,
    UploadIntent,
)
from artifacts.storage import ObjectMetadata, S3ObjectStorage

_DIGEST = "a" * 64


def test_upload_and_download_capabilities_are_single_object_and_short_lived() -> None:
    repository = _Repository()
    storage = _Storage()
    service = _service(repository, storage)

    upload = service.issue_upload(
        UploadIntent("application/pdf", "report.pdf", 42, _DIGEST, ArtifactPolicy(owner_id="run-1"))
    )

    record = repository.records[upload.artifact_id]
    assert upload.method == "PUT"
    assert storage.put_calls == [(record.storage_key, 60, "application/pdf", _DIGEST)]
    assert upload.required_headers == {
        "Content-Type": "application/pdf",
        "x-amz-meta-sha256": _DIGEST,
    }
    storage.objects[record.storage_key] = ObjectMetadata(42, "application/pdf", _DIGEST)

    finalized = service.finalize_upload(upload.artifact_id)
    download = service.issue_download(upload.artifact_id)

    assert finalized.state is ArtifactState.AVAILABLE
    assert download.method == "GET"
    assert storage.get_calls == [(record.storage_key, 60)]


@pytest.mark.parametrize(
    ("intent", "message"),
    [
        (UploadIntent("not a type", "report.pdf", 1, _DIGEST), "content type"),
        (UploadIntent("application/pdf", "../report.pdf", 1, _DIGEST), "filename"),
        (UploadIntent("application/pdf", "report.pdf", -1, _DIGEST), "byte length"),
        (UploadIntent("application/pdf", "report.pdf", 1, "not-a-digest"), "sha256"),
    ],
)
def test_upload_rejects_invalid_intent(intent: UploadIntent, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _service(_Repository(), _Storage()).issue_upload(intent)


@pytest.mark.parametrize(
    "metadata",
    [
        ObjectMetadata(41, "application/pdf", _DIGEST),
        ObjectMetadata(42, "text/plain", _DIGEST),
        ObjectMetadata(42, "application/pdf", "b" * 64),
        None,
    ],
)
def test_finalize_requires_head_metadata_to_match_upload_intent(
    metadata: ObjectMetadata | None,
) -> None:
    repository = _Repository()
    storage = _Storage()
    service = _service(repository, storage)
    upload = service.issue_upload(UploadIntent("application/pdf", "report.pdf", 42, _DIGEST))
    record = repository.records[upload.artifact_id]
    if metadata is not None:
        storage.objects[record.storage_key] = metadata

    with pytest.raises(ValueError):
        service.finalize_upload(upload.artifact_id)
    assert repository.records[upload.artifact_id].state is ArtifactState.PENDING_UPLOAD


def test_finalize_rejects_an_expired_upload_capability() -> None:
    repository = _Repository()
    storage = _Storage()
    service = _service(repository, storage)
    upload = service.issue_upload(UploadIntent("application/pdf", "report.pdf", 42, _DIGEST))
    record = repository.records[upload.artifact_id]
    repository.records[upload.artifact_id] = replace(
        record, expires_at=datetime.now(UTC) - timedelta(seconds=1)
    )

    with pytest.raises(ValueError, match="expired"):
        service.finalize_upload(upload.artifact_id)


def test_s3_capabilities_bind_bucket_key_type_and_checksum_metadata() -> None:
    client = _S3Client()
    storage = S3ObjectStorage(client, bucket="orrery-artifacts")

    assert storage.issue_put_url(
        key="artifacts/one", expires_in=60, content_type="text/csv", sha256=_DIGEST
    ) == "https://capability.invalid/put_object"
    assert storage.issue_get_url(key="artifacts/one", expires_in=60) == "https://capability.invalid/get_object"
    assert client.calls[0] == (
        "put_object",
        {
            "Bucket": "orrery-artifacts",
            "Key": "artifacts/one",
            "ContentType": "text/csv",
            "Metadata": {"sha256": _DIGEST},
        },
        60,
        "PUT",
    )


def test_settings_are_environment_based_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ORRERY_ARTIFACT_BUCKET", "orrery-artifacts")
    monkeypatch.setenv("ORRERY_ARTIFACT_CAPABILITY_TTL_SECONDS", "120")

    assert ArtifactCapabilitySettings.from_env() == ArtifactCapabilitySettings(
        bucket="orrery-artifacts", capability_ttl_seconds=120
    )


class _Repository:
    def __init__(self) -> None:
        self.records: dict[str, ArtifactRecord] = {}

    def create_pending(self, record: ArtifactRecord) -> ArtifactRecord:
        self.records[record.artifact_id] = record
        return record

    def get(self, artifact_id: str) -> ArtifactRecord | None:
        return self.records.get(artifact_id)

    def mark_available(self, artifact_id: str) -> bool:
        record = self.records.get(artifact_id)
        if record is None or record.state is not ArtifactState.PENDING_UPLOAD:
            return False
        self.records[artifact_id] = ArtifactRecord(
            **{**record.__dict__, "state": ArtifactState.AVAILABLE}
        )
        return True


class _Storage:
    def __init__(self) -> None:
        self.objects: dict[str, ObjectMetadata] = {}
        self.put_calls: list[tuple[str, int, str, str]] = []
        self.get_calls: list[tuple[str, int]] = []

    def issue_put_url(self, *, key: str, expires_in: int, content_type: str, sha256: str) -> str:
        self.put_calls.append((key, expires_in, content_type, sha256))
        return f"https://capability.invalid/upload/{key}"

    def issue_get_url(self, *, key: str, expires_in: int) -> str:
        self.get_calls.append((key, expires_in))
        return f"https://capability.invalid/download/{key}"

    def head(self, *, key: str) -> ObjectMetadata | None:
        return self.objects.get(key)


class _S3Client:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object], int, str]] = []

    def generate_presigned_url(
        self, operation: str, *, Params: dict[str, object], ExpiresIn: int, HttpMethod: str
    ) -> str:
        self.calls.append((operation, Params, ExpiresIn, HttpMethod))
        return f"https://capability.invalid/{operation}"


def _service(repository: _Repository, storage: _Storage) -> ArtifactCapabilityService:
    return ArtifactCapabilityService(
        repository, storage, ArtifactCapabilitySettings(bucket="unused", capability_ttl_seconds=60)
    )
