"""#131 public proxy delivery preserves metadata and never leaks capability URLs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from chirp.testing import TestClient

from artifacts.delivery import DownloadAuditEvent
from artifacts.domain import ArtifactPolicy, ArtifactRecord, ArtifactState
from artifacts.storage import InMemoryObjectStorage
from stars.html_to_pdf.artifacts import (
    DurablePdfArtifactService,
    InMemoryPdfArtifactRepository,
    UnconfiguredPdfArtifactService,
    configure_pdf_artifacts,
)


class _Audit:
    def __init__(self) -> None:
        self.events: list[DownloadAuditEvent] = []

    def record(self, event: DownloadAuditEvent) -> None:
        self.events.append(event)


@pytest.mark.asyncio
async def test_proxy_serves_stored_pdf_csv_and_png_metadata(example_app) -> None:
    audit = _Audit()
    service = DurablePdfArtifactService(
        InMemoryPdfArtifactRepository(), InMemoryObjectStorage(), audit=audit
    )
    configure_pdf_artifacts(service)
    published = [
        (
            service.publish(b"%PDF-", content_type="application/pdf", filename="report.pdf"),
            "application/pdf",
            "report.pdf",
        ),
        (
            service.publish(
                b"name,count\nOrrery,1\n", content_type="text/csv", filename="report.csv"
            ),
            "text/csv",
            "report.csv",
        ),
        (
            service.publish(b"\x89PNG\r\n\x1a\n", content_type="image/png", filename="image.png"),
            "image/png",
            "image.png",
        ),
    ]
    async with TestClient(example_app) as client:
        responses = [
            await client.get(f"/artifacts/{artifact.artifact_id}") for artifact, _, _ in published
        ]
    for response, (_, content_type, filename) in zip(responses, published, strict=True):
        assert response.status == 200
        assert response.content_type == content_type
        assert f'filename="{filename}"' in (response.header("Content-Disposition") or "")
        assert response.header("Cache-Control") == "no-store"
        assert response.header("X-Content-Type-Options") == "nosniff"
    assert [event.outcome for event in audit.events] == ["served", "served", "served"]


@pytest.mark.asyncio
async def test_proxy_rejections_are_no_store_and_hostile_filename_is_safe(example_app) -> None:
    audit = _Audit()
    service = DurablePdfArtifactService(
        InMemoryPdfArtifactRepository(), InMemoryObjectStorage(), audit=audit
    )
    configure_pdf_artifacts(service)
    artifact = service.publish(
        b"name,count\n", content_type="text/csv", filename="../report\r\nX-Injected: yes.csv"
    )
    async with TestClient(example_app) as client:
        served = await client.get(f"/artifacts/{artifact.artifact_id}")
        missing = await client.get("/artifacts/not-a-real-artifact")
        configure_pdf_artifacts(UnconfiguredPdfArtifactService("test unavailable"))
        unavailable = await client.get("/artifacts/any")
    header = served.header("Content-Disposition") or ""
    assert "\r" not in header and "\n" not in header and ":" not in header
    assert 'filename="report_X-Injected_yes.csv"' in header
    for response, status in ((missing, 404), (unavailable, 503)):
        assert response.status == status
        assert response.header("Cache-Control") == "no-store"
        assert response.header("X-Content-Type-Options") == "nosniff"


def test_private_policy_and_expiry_are_rejected_and_audit_is_url_free() -> None:
    audit = _Audit()
    repository, storage = InMemoryPdfArtifactRepository(), InMemoryObjectStorage()
    now = datetime(2026, 8, 9, tzinfo=UTC)
    service = DurablePdfArtifactService(repository, storage, clock=lambda: now, audit=audit)
    record = ArtifactRecord(
        "private-id",
        "artifacts/private-id",
        "a" * 64,
        1,
        "text/csv",
        "secret.csv",
        now + timedelta(minutes=1),
        ArtifactPolicy(access="private", owner_id="agent:a"),
        ArtifactState.AVAILABLE,
    )
    repository.records[record.artifact_id] = record
    storage.put(key=record.storage_key, data=b"x", content_type=record.content_type)
    assert service.download(record.artifact_id, owner_id="agent:b") is None
    expired = ArtifactRecord(**{**record.__dict__, "artifact_id": "expired", "expires_at": now})
    repository.records[expired.artifact_id] = expired
    assert service.download(expired.artifact_id, owner_id="agent:a") is None
    assert [event.outcome for event in audit.events] == ["denied", "not_available"]
    assert all("url" not in event.__dict__ for event in audit.events)
    leaked = "https://capability.example/download?sig=secret"
    assert service.download(leaked) is None
    assert audit.events[-1].artifact_id.startswith("sha256:")
    assert leaked not in audit.events[-1].artifact_id
