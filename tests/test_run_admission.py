"""Acceptance coverage for #159 managed-run admission, quotas, and cancellation."""

from __future__ import annotations

from datetime import timedelta

import pytest

from artifacts.storage import InMemoryObjectStorage
from runs import (
    InMemoryQueueBackend,
    InMemoryRunRepository,
    ManagedRunSubmission,
    ManagedRunWorker,
    RunAdmissionError,
    RunState,
    RunWorkerRuntime,
    WorkerSettings,
)
from runs.admission import serialized_input_bytes
from stars.cpu_workloads import build_registry
from stars.html_to_pdf.artifacts import DurablePdfArtifactService, InMemoryPdfArtifactRepository
from stars.managed_api import ManagedAdmissionRejected, ManagedStarService

pytestmark = pytest.mark.issue(159)


def _system(*, max_active: int | None = None):
    artifacts = DurablePdfArtifactService(InMemoryPdfArtifactRepository(), InMemoryObjectStorage())
    repository = InMemoryRunRepository()
    queue = InMemoryQueueBackend()
    worker = ManagedRunWorker(repository, queue, max_attempts=2, retry_after=timedelta(0))
    submit = ManagedRunSubmission(worker)
    runtime = RunWorkerRuntime(
        worker,
        build_registry(artifacts),
        WorkerSettings("postgres://example", "redis://example", "cpu-test", max_attempts=2),
    )
    service = ManagedStarService(submit, repository, worker=worker)
    return submit, worker, runtime, repository, queue, service, max_active


def _submit_many(submit: ManagedRunSubmission, caller_id: str, count: int) -> None:
    for index in range(count):
        submit.submit(
            caller_id=caller_id,
            idempotency_key=f"seed-{index}",
            kind="csv-report",
            input={"rows": [{"n": index}]},
        )


def test_over_limit_input_is_rejected_before_enqueue() -> None:
    submit, _worker, _, repository, queue, service, _ = _system()
    huge_rows = [{"value": "x" * 2048} for _ in range(600)]
    with pytest.raises(RunAdmissionError) as error:
        submit.submit(
            caller_id="agent:a",
            idempotency_key="too-big",
            kind="csv-report",
            input={"rows": huge_rows},
        )
    assert error.value.code == "input_too_large"
    assert error.value.policy["max_input_bytes"] == 1_048_576
    assert queue.stats().ready_depth == 0
    assert repository.list_by_states(RunState.ACCEPTED, RunState.QUEUED) == ()

    with pytest.raises(ManagedAdmissionRejected) as managed_error:
        service.submit(
            caller_id="agent:a",
            idempotency_key="too-big-mcp",
            kind="csv-report",
            input={"rows": huge_rows},
        )
    assert managed_error.value.code == "input_too_large"
    assert "run-" not in str(managed_error.value.policy)


def test_concurrency_cap_rejects_without_leaking_other_tenants() -> None:
    submit, _worker, _, _repository, queue, service, _ = _system()
    _submit_many(submit, "agent:alice", 3)
    _submit_many(submit, "agent:bob", 2)
    depth_before = queue.stats().ready_depth

    with pytest.raises(RunAdmissionError) as error:
        submit.submit(
            caller_id="agent:alice",
            idempotency_key="fourth",
            kind="csv-report",
            input={"rows": [{"n": 1}]},
        )
    assert error.value.code == "concurrency_exhausted"
    assert error.value.policy == {"max_active_per_caller": 3, "active": 3}
    assert queue.stats().ready_depth == depth_before
    assert "agent:bob" not in str(error.value.policy)
    assert "run-agent-bob" not in str(error.value.policy)

    with pytest.raises(ManagedAdmissionRejected) as managed_error:
        service.submit(
            caller_id="agent:alice",
            idempotency_key="fourth-mcp",
            kind="csv-report",
            input={"rows": [{"n": 1}]},
        )
    assert managed_error.value.code == "concurrency_exhausted"
    assert "agent:bob" not in str(managed_error.value.policy)


def test_idempotent_submit_replay_returns_original_despite_quota() -> None:
    submit, _, _, _repository, _, _, _ = _system()
    first = submit.submit(
        caller_id="agent:alice",
        idempotency_key="replay-me",
        kind="csv-report",
        input={"rows": [{"n": 1}]},
    )
    _submit_many(submit, "agent:alice", 2)
    replay = submit.submit(
        caller_id="agent:alice",
        idempotency_key="replay-me",
        kind="csv-report",
        input={"rows": [{"n": 999}]},
    )
    assert replay.run_id == first.run_id
    assert replay.state is RunState.QUEUED


def test_cancel_before_claim_is_terminal_and_queue_is_empty() -> None:
    submit, _worker, _, repository, queue, service, _ = _system()
    run = submit.submit(
        caller_id="agent:a",
        idempotency_key="cancel-me",
        kind="csv-report",
        input={"rows": [{"n": 1}]},
    )
    assert queue.stats().ready_depth == 1
    payload = service.cancel(run_id=run.run_id, caller_id="agent:a")
    assert payload == {"run_id": run.run_id, "state": "cancelled"}
    sealed = repository.get(run.run_id)
    assert sealed is not None and sealed.state is RunState.CANCELLED
    assert sealed.terminal_receipt == {"kind": "cancel", "code": "caller_cancelled"}
    assert queue.stats().ready_depth == 0
    result = service.result(run.run_id)
    assert result["state"] == "cancelled"
    assert result["terminal_reason"] == "caller_cancelled"
    replay = service.cancel(run_id=run.run_id, caller_id="agent:a")
    assert replay["state"] == "cancelled"


def test_cancel_during_lease_prevents_successful_seal() -> None:
    submit, worker, _runtime, repository, queue, service, _ = _system()
    run = submit.submit(
        caller_id="agent:a",
        idempotency_key="lease-cancel",
        kind="csv-report",
        input={"rows": [{"n": 1}]},
    )
    lease = worker.claim("worker-a")
    assert lease is not None
    service.cancel(run_id=run.run_id, caller_id="agent:a")
    assert repository.get(run.run_id).state is RunState.CANCELLED  # type: ignore[union-attr]
    assert not worker.succeed(lease, receipt={"artifact_id": "art-1"})
    assert repository.get(run.run_id).state is RunState.CANCELLED  # type: ignore[union-attr]
    assert queue.stats().leased_depth == 0


def test_unauthorized_cancel_and_result_do_not_leak_other_callers() -> None:
    submit, _worker, _, _repository, _, service, _ = _system()
    run = submit.submit(
        caller_id="agent:alice",
        idempotency_key="private",
        kind="csv-report",
        input={"rows": [{"n": 1}]},
    )
    cancel_error = service.cancel(run_id=run.run_id, caller_id="agent:mallory")
    assert cancel_error == {"error": "run_not_found", "run_id": run.run_id}
    result_error = service.result("does-not-exist")
    assert result_error == {"error": "run_not_found", "run_id": "does-not-exist"}


def test_accepted_run_stores_budget_policy_snapshot() -> None:
    submit, _, _, repository, _, _, _ = _system()
    run = submit.submit(
        caller_id="agent:a",
        idempotency_key="budget",
        kind="image-transform",
        input={"color": "#112233"},
    )
    stored = repository.get(run.run_id)
    assert stored is not None
    assert stored.budget["executor"] == "managed-cpu-worker"
    policy = stored.budget["policy"]
    assert policy["cpu_millicores"] == 250
    assert policy["wall_time_seconds"] == 30
    assert policy["max_output_bytes"] == 1_048_576
    assert policy["max_input_bytes"] == 1_048_576


def test_serialized_input_bytes_is_stable() -> None:
    assert serialized_input_bytes({"b": 1, "a": 2}) == serialized_input_bytes({"a": 2, "b": 1})
