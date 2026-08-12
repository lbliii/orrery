"""#133: CPU specimens execute only in the separate durable worker runtime."""

from __future__ import annotations

from datetime import timedelta

from artifacts.storage import InMemoryObjectStorage
from runs import (
    InMemoryQueueBackend,
    InMemoryRunRepository,
    ManagedRunSubmission,
    ManagedRunWorker,
    RunState,
    RunWorkerRuntime,
    WorkerSettings,
)
from stars.cpu_workloads import build_registry
from stars.html_to_pdf.artifacts import DurablePdfArtifactService, InMemoryPdfArtifactRepository
from stars.html_to_pdf.skill import build_skill as build_pdf_skill
from stars.managed_api import ManagedStarService


def _system(*, attempts: int = 2):
    artifacts = DurablePdfArtifactService(InMemoryPdfArtifactRepository(), InMemoryObjectStorage())
    repository = InMemoryRunRepository()
    queue = InMemoryQueueBackend()
    worker = ManagedRunWorker(repository, queue, max_attempts=attempts, retry_after=timedelta(0))
    runtime = RunWorkerRuntime(
        worker,
        build_registry(artifacts),
        WorkerSettings("postgres://example", "redis://example", "cpu-test", max_attempts=attempts),
    )
    return ManagedRunSubmission(worker), runtime, repository, artifacts, queue


def test_pdf_csv_and_png_are_queued_then_executed_by_the_worker_with_durable_receipts() -> None:
    submit, runtime, repository, artifacts, _ = _system()
    jobs = [
        ("html-to-pdf", {"html": "<h1>Orrery</h1>"}, "application/pdf", b"%PDF-"),
        ("csv-report", {"rows": [{"star": "Orrery", "count": 1}]}, "text/csv", b"count,star"),
        ("image-transform", {"color": "#102030"}, "image/png", b"\x89PNG"),
    ]
    for index, (kind, payload, content_type, prefix) in enumerate(jobs):
        run = submit.submit(
            caller_id="agent:test", idempotency_key=f"job-{index}", kind=kind, input=payload
        )
        assert run.state is RunState.QUEUED
        assert runtime.process_once()
        sealed = repository.get(run.run_id)
        assert sealed is not None and sealed.state is RunState.SUCCEEDED
        receipt = sealed.terminal_receipt
        assert receipt is not None
        assert receipt["executor"] == "managed-cpu-worker"
        assert receipt["workload"] == kind
        assert receipt["policy"]["wall_time_seconds"] == 30
        assert receipt["content_type"] == content_type
        delivered = artifacts.download(str(receipt["artifact_id"]))
        assert delivered is not None and delivered[1].startswith(prefix)
        assert receipt["sha256"] == f"sha256:{delivered[0].sha256}"


def test_bad_workload_retries_then_dead_letters_without_an_artifact() -> None:
    submit, runtime, repository, _, queue = _system(attempts=2)
    run = submit.submit(
        caller_id="agent:test",
        idempotency_key="bad-color",
        kind="image-transform",
        input={"color": "bad"},
    )
    assert runtime.process_once()  # handler error: retry
    assert repository.get(run.run_id).state is RunState.RUNNING  # type: ignore[union-attr]
    assert runtime.process_once()  # second failure: dead letter and seal
    sealed = repository.get(run.run_id)
    assert sealed is not None and sealed.state is RunState.FAILED
    assert sealed.terminal_reason == "handler_error"
    assert queue.dead_letters()[0]["attempts"] == 2


def test_pdf_mcp_submit_is_queued_then_result_is_an_envelope_signed_final_receipt() -> None:
    submit, runtime, repository, _, _ = _system()
    service = ManagedStarService(submit, repository)
    skill = build_pdf_skill(managed_service=service)
    submit_handler = next(tool for tool in skill._pending if tool.name == "submit").handler
    queued = submit_handler(html="<p>queued</p>", idempotency_key="mcp-pdf")
    run_id = queued.payload["run_id"]
    assert queued.payload["state"] == "queued"
    result_handler = next(tool for tool in skill._pending if tool.name == "result").handler
    pending = result_handler(run_id=run_id)
    assert pending.payload == {"run_id": run_id, "state": "queued"}
    assert runtime.process_once()
    final = result_handler(run_id=run_id)
    assert final.payload["state"] == "succeeded"
    assert final.payload["receipt"]["executor"] == "managed-cpu-worker"
    # Chirp's returned Envelope (not a hand-written dict) signs the final receipt payload.
    assert final.signature


def test_pdf_mcp_result_unknown_run_id_returns_structured_run_not_found() -> None:
    submit, _, repository, _, _ = _system()
    service = ManagedStarService(submit, repository)
    skill = build_pdf_skill(managed_service=service)
    result_handler = next(tool for tool in skill._pending if tool.name == "result").handler
    envelope = result_handler(run_id="does-not-exist")
    assert envelope.payload == {"error": "run_not_found", "run_id": "does-not-exist"}
