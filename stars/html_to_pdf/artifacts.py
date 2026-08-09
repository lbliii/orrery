"""Durable delivery for PDFs emitted by the html-to-pdf Star.

Bytes are deliberately kept behind the generic :mod:`artifacts` ports.  A
worker may publish a PDF and a different web process may subsequently serve
it; neither process needs to retain the bytes in memory.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from artifacts import ArtifactPolicy, ArtifactRecord, ArtifactState, ArtifactStorage
from artifacts.domain import artifact_storage_key, new_artifact_id
from artifacts.storage import InMemoryObjectStorage, S3ObjectStorage

PDF_ARTIFACT_TTL_SECONDS = 15 * 60


class ArtifactDeliveryUnavailable(RuntimeError):
    """Raised when this deployment cannot safely publish or retrieve artifacts."""


@dataclass(frozen=True)
class PdfArtifact:
    """Delivery metadata; PDF bytes live in object storage, never this object."""

    artifact_id: str
    sha256: str
    expires_at: datetime


class PdfArtifactRepository:
    """Small repository boundary needed by the synchronous PDF delivery path."""

    def create_pending(self, record: ArtifactRecord) -> ArtifactRecord: ...

    def get(self, artifact_id: str) -> ArtifactRecord | None: ...

    def mark_available(self, artifact_id: str) -> bool: ...


class DurablePdfArtifactService:
    """Publish immutable PDFs to durable storage and retrieve them by opaque ID."""

    def __init__(
        self,
        repository: PdfArtifactRepository,
        storage: ArtifactStorage,
        *,
        ttl_seconds: int = PDF_ARTIFACT_TTL_SECONDS,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._ttl_seconds = ttl_seconds
        self._clock = clock or (lambda: datetime.now(UTC))

    def publish(
        self,
        data: bytes,
        *,
        content_type: str = "application/pdf",
        filename: str | None = None,
    ) -> PdfArtifact:
        now = self._clock()
        artifact_id = new_artifact_id()
        digest = hashlib.sha256(data).hexdigest()
        record = ArtifactRecord(
            artifact_id=artifact_id,
            storage_key=artifact_storage_key(artifact_id),
            sha256=digest,
            byte_length=len(data),
            content_type=content_type,
            filename=filename or f"{artifact_id}{_extension_for(content_type)}",
            expires_at=now + timedelta(seconds=self._ttl_seconds),
            policy=ArtifactPolicy(access="receipt-holder", retention_class="ephemeral"),
        )
        self._repository.create_pending(record)
        try:
            self._storage.put(key=record.storage_key, data=data, content_type=record.content_type)
            if not self._repository.mark_available(record.artifact_id):
                raise ArtifactDeliveryUnavailable("artifact publication could not be finalized")
        except Exception:
            # Never leave an apparently downloadable record after a partial publish.
            self._storage.delete(key=record.storage_key)
            raise
        return PdfArtifact(record.artifact_id, f"sha256:{digest}", record.expires_at)

    def download(self, artifact_id: str) -> tuple[ArtifactRecord, bytes] | None:
        record = self._repository.get(artifact_id)
        if (
            record is None
            or record.state is not ArtifactState.AVAILABLE
            or record.expires_at <= self._clock()
        ):
            return None
        data = self._storage.get(key=record.storage_key)
        if data is None:
            return None
        if len(data) != record.byte_length or hashlib.sha256(data).hexdigest() != record.sha256:
            raise ArtifactDeliveryUnavailable("artifact integrity check failed")
        return record, data

    def health(self) -> dict[str, str]:
        return {"status": "ok", "artifact_delivery": "durable"}


class InMemoryPdfArtifactRepository:
    """Explicit test/development repository, intentionally not process-shared."""

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


class UnconfiguredPdfArtifactService:
    """Fails closed until an operator configures durable delivery."""

    def __init__(self, reason: str) -> None:
        self.reason = reason

    def publish(self, data: bytes, **_: object) -> PdfArtifact:
        raise ArtifactDeliveryUnavailable(self.reason)

    def download(self, artifact_id: str) -> tuple[ArtifactRecord, bytes] | None:
        raise ArtifactDeliveryUnavailable(self.reason)

    def health(self) -> dict[str, str]:
        return {"status": "degraded", "artifact_delivery": "unconfigured", "reason": self.reason}


def configured_pdf_artifacts() -> DurablePdfArtifactService | UnconfiguredPdfArtifactService:
    """Build the process-independent service from deployment configuration.

    ``memory`` is only an explicit local/test mode. Production requires both
    Postgres metadata (``DATABASE_URL``) and an S3-compatible bucket.
    """
    backend = os.environ.get("ORRERY_ARTIFACT_BACKEND", "").strip().lower()
    if backend == "memory":
        return DurablePdfArtifactService(InMemoryPdfArtifactRepository(), InMemoryObjectStorage())
    if backend not in {"s3", "railway-bucket"}:
        return UnconfiguredPdfArtifactService(
            "durable artifact delivery is unconfigured; set ORRERY_ARTIFACT_BACKEND=s3"
        )
    bucket = os.environ.get("ORRERY_ARTIFACT_BUCKET", "").strip()
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not bucket or not database_url:
        return UnconfiguredPdfArtifactService(
            "durable artifact delivery requires ORRERY_ARTIFACT_BUCKET and DATABASE_URL"
        )
    try:
        import boto3
        import psycopg

        from artifacts import PostgresArtifactRepository

        client = boto3.client(
            "s3",
            endpoint_url=os.environ.get("ORRERY_ARTIFACT_ENDPOINT") or None,
            region_name=os.environ.get("AWS_REGION") or None,
        )
        repository = PostgresArtifactRepository(lambda: psycopg.connect(database_url))
        repository.initialize()
        return DurablePdfArtifactService(repository, S3ObjectStorage(client, bucket=bucket))
    except Exception as exc:
        return UnconfiguredPdfArtifactService(f"durable artifact delivery unavailable: {exc}")


pdf_artifacts: DurablePdfArtifactService | UnconfiguredPdfArtifactService = (
    configured_pdf_artifacts()
)


def get_pdf_artifacts() -> DurablePdfArtifactService | UnconfiguredPdfArtifactService:
    """Return the current service so test/app wiring is not captured at import time."""
    return pdf_artifacts


def configure_pdf_artifacts(
    service: DurablePdfArtifactService | UnconfiguredPdfArtifactService,
) -> None:
    """Inject a service for app construction and focused integration tests."""
    global pdf_artifacts
    pdf_artifacts = service


def _extension_for(content_type: str) -> str:
    return {"application/pdf": ".pdf", "text/csv": ".csv", "image/png": ".png"}.get(
        content_type, ".bin"
    )
