"""Cross-worker durable delivery coverage for GitHub issue #128."""

from __future__ import annotations

import hashlib

import pytest

from artifacts.storage import InMemoryObjectStorage
from stars.html_to_pdf.artifacts import (
    ArtifactDeliveryUnavailable,
    DurablePdfArtifactService,
    InMemoryPdfArtifactRepository,
    UnconfiguredPdfArtifactService,
)
from stars.html_to_pdf.service import health


@pytest.mark.issue(128)
def test_durable_pdf_is_retrievable_by_a_different_web_process() -> None:
    """Separate service instances emulate a renderer worker and web worker."""
    repository = InMemoryPdfArtifactRepository()
    storage = InMemoryObjectStorage()
    renderer = DurablePdfArtifactService(repository, storage)
    web = DurablePdfArtifactService(repository, storage)

    emitted = renderer.publish(b"%PDF-1.4\nproof\n%%EOF\n")
    delivered = web.download(emitted.artifact_id)

    assert delivered is not None
    record, data = delivered
    assert emitted.sha256 == f"sha256:{hashlib.sha256(data).hexdigest()}"
    assert record.sha256 == hashlib.sha256(data).hexdigest()


@pytest.mark.issue(128)
def test_process_local_storage_regression_is_not_a_delivery_backend() -> None:
    """The old per-process dictionary shape fails when the request is routed elsewhere."""
    renderer = DurablePdfArtifactService(InMemoryPdfArtifactRepository(), InMemoryObjectStorage())
    unrelated_web_worker = DurablePdfArtifactService(
        InMemoryPdfArtifactRepository(), InMemoryObjectStorage()
    )

    emitted = renderer.publish(b"%PDF-1.4\nprocess-bound\n%%EOF\n")

    assert unrelated_web_worker.download(emitted.artifact_id) is None


@pytest.mark.issue(128)
def test_unconfigured_delivery_fails_closed_for_publish_and_download() -> None:
    service = UnconfiguredPdfArtifactService("missing bucket and database")

    with pytest.raises(ArtifactDeliveryUnavailable, match="missing bucket"):
        service.publish(b"%PDF-")
    with pytest.raises(ArtifactDeliveryUnavailable, match="missing bucket"):
        service.download("opaque-id")


@pytest.mark.issue(128)
def test_health_reports_degraded_when_durable_delivery_is_unconfigured() -> None:
    from stars.html_to_pdf.artifacts import configure_pdf_artifacts

    configure_pdf_artifacts(UnconfiguredPdfArtifactService("missing bucket and database"))

    assert health() == {
        "status": "degraded",
        "skill": "html-to-pdf",
        "artifact_delivery": "unconfigured",
        "reason": "missing bucket and database",
    }
