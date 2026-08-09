"""Scoped artifact upload/download capabilities and integrity finalization."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Protocol

from .domain import (
    ArtifactPolicy,
    ArtifactRecord,
    ArtifactState,
    artifact_storage_key,
    expires_at_after,
    new_artifact_id,
)
from .storage import CapabilityObjectStorage

_SHA256 = re.compile(r"^(?:sha256:)?([0-9a-fA-F]{64})$")
_CONTENT_TYPE = re.compile(
    r"^[^\x00-\x1f\x7f;/]{1,127}/[^\x00-\x1f\x7f;]{1,127}(?:;[^\x00-\x1f\x7f]{1,127})?$"
)


class ArtifactRepository(Protocol):
    def create_pending(self, record: ArtifactRecord) -> ArtifactRecord: ...

    def get(self, artifact_id: str) -> ArtifactRecord | None: ...

    def mark_available(self, artifact_id: str) -> bool: ...


@dataclass(frozen=True)
class ArtifactCapabilitySettings:
    """Non-secret configuration; SDK credential resolution stays outside Orrery."""

    bucket: str
    capability_ttl_seconds: int = 300
    max_byte_length: int = 25 * 1024 * 1024

    @classmethod
    def from_env(cls) -> ArtifactCapabilitySettings:
        """Read deployment config without loading, logging, or embedding credentials."""
        bucket = os.environ.get("ORRERY_ARTIFACT_BUCKET", "").strip()
        if not bucket:
            raise ValueError("ORRERY_ARTIFACT_BUCKET must be configured")
        return cls(
            bucket=bucket,
            capability_ttl_seconds=_positive_int(
                "ORRERY_ARTIFACT_CAPABILITY_TTL_SECONDS", 300, maximum=3600
            ),
            max_byte_length=_positive_int(
                "ORRERY_ARTIFACT_MAX_BYTES", 25 * 1024 * 1024, maximum=5 * 1024**3
            ),
        )


@dataclass(frozen=True)
class UploadIntent:
    content_type: str
    filename: str
    byte_length: int
    sha256: str
    policy: ArtifactPolicy = field(default_factory=ArtifactPolicy)


@dataclass(frozen=True)
class ObjectCapability:
    artifact_id: str
    url: str
    method: str
    expires_at: datetime
    required_headers: dict[str, str]


class ArtifactCapabilityService:
    """Issue least-privilege object URLs and finalize only verified uploads."""

    def __init__(
        self,
        repository: ArtifactRepository,
        storage: CapabilityObjectStorage,
        settings: ArtifactCapabilitySettings,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._settings = settings

    def issue_upload(self, intent: UploadIntent) -> ObjectCapability:
        normalized = _validate_intent(intent, max_byte_length=self._settings.max_byte_length)
        artifact_id = new_artifact_id()
        record = ArtifactRecord(
            artifact_id=artifact_id,
            storage_key=artifact_storage_key(artifact_id),
            sha256=normalized.sha256,
            byte_length=normalized.byte_length,
            content_type=normalized.content_type,
            filename=normalized.filename,
            expires_at=expires_at_after(self._settings.capability_ttl_seconds),
            policy=normalized.policy,
        )
        self._repository.create_pending(record)
        return ObjectCapability(
            artifact_id=artifact_id,
            url=self._storage.issue_put_url(
                key=record.storage_key,
                expires_in=self._settings.capability_ttl_seconds,
                content_type=record.content_type,
                sha256=record.sha256,
            ),
            method="PUT",
            expires_at=record.expires_at,
            required_headers={
                "Content-Type": record.content_type,
                "x-amz-meta-sha256": record.sha256,
            },
        )

    def finalize_upload(self, artifact_id: str) -> ArtifactRecord:
        record = self._pending_record(artifact_id)
        if record.expires_at <= datetime.now(UTC):
            raise ValueError("artifact upload capability has expired")
        object_metadata = self._storage.head(key=record.storage_key)
        if object_metadata is None:
            raise ValueError("artifact object is missing")
        if object_metadata.byte_length != record.byte_length:
            raise ValueError("artifact byte length does not match upload intent")
        if object_metadata.content_type != record.content_type:
            raise ValueError("artifact content type does not match upload intent")
        if object_metadata.sha256 != record.sha256:
            raise ValueError("artifact sha256 does not match upload intent")
        if not self._repository.mark_available(artifact_id):
            raise ValueError("artifact could not be finalized")
        return replace(record, state=ArtifactState.AVAILABLE)

    def issue_download(self, artifact_id: str) -> ObjectCapability:
        record = self._repository.get(artifact_id)
        if record is None or record.state is not ArtifactState.AVAILABLE:
            raise ValueError("artifact is not available")
        if record.expires_at <= datetime.now(UTC):
            raise ValueError("artifact has expired")
        return ObjectCapability(
            artifact_id=record.artifact_id,
            url=self._storage.issue_get_url(
                key=record.storage_key, expires_in=self._settings.capability_ttl_seconds
            ),
            method="GET",
            expires_at=expires_at_after(self._settings.capability_ttl_seconds),
            required_headers={},
        )

    def _pending_record(self, artifact_id: str) -> ArtifactRecord:
        record = self._repository.get(artifact_id)
        if record is None or record.state is not ArtifactState.PENDING_UPLOAD:
            raise ValueError("artifact is not awaiting upload")
        return record


def _validate_intent(intent: UploadIntent, *, max_byte_length: int) -> UploadIntent:
    if not isinstance(intent.byte_length, int) or isinstance(intent.byte_length, bool):
        raise ValueError("artifact byte length must be an integer")
    if not 0 <= intent.byte_length <= max_byte_length:
        raise ValueError(f"artifact byte length must be between 0 and {max_byte_length}")
    if not _CONTENT_TYPE.fullmatch(intent.content_type):
        raise ValueError("invalid artifact content type")
    if not intent.filename or len(intent.filename) > 255 or any(
        character in intent.filename for character in ("/", "\\", "\x00", "\r", "\n")
    ):
        raise ValueError("invalid artifact filename")
    digest = _SHA256.fullmatch(intent.sha256)
    if digest is None:
        raise ValueError("artifact sha256 must be a SHA-256 hex digest")
    return UploadIntent(
        content_type=intent.content_type,
        filename=intent.filename,
        byte_length=intent.byte_length,
        sha256=digest.group(1).lower(),
        policy=intent.policy,
    )


def _positive_int(name: str, default: int, *, maximum: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not 0 < value <= maximum:
        raise ValueError(f"{name} must be between 1 and {maximum}")
    return value
