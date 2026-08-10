"""Acceptance coverage for #158 managed-run reconciliation audits."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from runs import (
    InMemoryAuditLog,
    InMemoryQueueBackend,
    InMemoryRunRepository,
    JobHandlerRegistry,
    ManagedRunWorker,
    RunReconciler,
    RunRecord,
    RunState,
    RunWorkerRuntime,
    WorkerSettings,
)
from runs.domain import RunConflictError


class _Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now = self.now + timedelta(seconds=seconds)


def _stack(
    *, max_attempts: int = 1
) -> tuple[
    RunWorkerRuntime,
    InMemoryRunRepository,
    InMemoryQueueBackend,
    JobHandlerRegistry,
    _Clock,
    InMemoryAuditLog,
]:
    clock = _Clock()
    repository = InMemoryRunRepository(clock=clock)
    queue = InMemoryQueueBackend(clock=clock)
    audit = InMemoryAuditLog()
    worker = ManagedRunWorker(
        repository,
        queue,
        max_attempts=max_attempts,
        lease_for=timedelta(seconds=3),
        retry_after=timedelta(0),
    )
    settings = WorkerSettings(
        "postgres://example",
        "redis://example",
        "test-worker",
        max_attempts=max_attempts,
        lease_seconds=3,
    )
    registry = JobHandlerRegistry()
    runtime = RunWorkerRuntime(
        worker,
        registry,
        settings,
        reconciler=RunReconciler(repository, queue, audit, clock=clock),
        audit=audit,
    )
    return runtime, repository, queue, registry, clock, audit


def test_lease_expiry_dead_letter_seals_postgres_with_audit() -> None:
    runtime, repository, queue, registry, clock, audit = _stack(max_attempts=1)
    repository.create_or_get(
        RunRecord("run-1", "agent:a", "k1", {}, "managed-cpu", job={"kind": "slow"})
    )
    runtime._worker.enqueue("run-1")
    registry.register("slow", lambda _record: (_ for _ in ()).throw(RuntimeError("stall")))

    lease = runtime._worker.claim("test-worker")
    assert lease is not None
    clock.advance(5)
    assert queue.recover_expired(max_attempts=1) == 1
    events = runtime._reconciler.reconcile_once()
    run = repository.get("run-1")
    assert run is not None and run.state is RunState.FAILED
    assert run.terminal_reason == "lease_expired_attempt_limit"
    assert any(event.kind == "dead_letter_sealed" for event in events)
    assert audit.counts_by_kind()["dead_letter_sealed"] == 1


def test_orphaned_running_run_is_sealed_with_audit() -> None:
    clock = _Clock()
    repository = InMemoryRunRepository(clock=clock)
    queue = InMemoryQueueBackend(clock=clock)
    audit = InMemoryAuditLog()
    repository.create_or_get(
        RunRecord("run-orphan", "agent:a", "k2", {}, "managed-cpu", job={"kind": "x"})
    )
    repository.transition("run-orphan", from_state=RunState.ACCEPTED, to_state=RunState.QUEUED)
    repository.transition("run-orphan", from_state=RunState.QUEUED, to_state=RunState.RUNNING)
    reconciler = RunReconciler(repository, queue, audit, clock=clock)

    events = reconciler.reconcile_once()
    run = repository.get("run-orphan")
    assert run is not None and run.state is RunState.FAILED
    assert run.terminal_reason == "orphaned_running"
    assert events[0].kind == "orphan_sealed"
    assert events[0].as_dict()["evidence"]["to"] == "failed"


def test_queued_missing_from_queue_is_requeued() -> None:
    clock = _Clock()
    repository = InMemoryRunRepository(clock=clock)
    queue = InMemoryQueueBackend(clock=clock)
    audit = InMemoryAuditLog()
    repository.create_or_get(
        RunRecord("run-q", "agent:a", "k3", {}, "managed-cpu", job={"kind": "x"})
    )
    repository.transition("run-q", from_state=RunState.ACCEPTED, to_state=RunState.QUEUED)
    reconciler = RunReconciler(repository, queue, audit, clock=clock)

    events = reconciler.reconcile_once()
    assert "run-q" in queue.active_run_ids()
    assert events[0].kind == "orphan_requeued"


def test_terminal_postgres_drops_stale_queue_job() -> None:
    clock = _Clock()
    repository = InMemoryRunRepository(clock=clock)
    queue = InMemoryQueueBackend(clock=clock)
    audit = InMemoryAuditLog()
    repository.create_or_get(
        RunRecord("run-done", "agent:a", "k4", {}, "managed-cpu", job={"kind": "x"})
    )
    repository.transition("run-done", from_state=RunState.ACCEPTED, to_state=RunState.QUEUED)
    repository.transition("run-done", from_state=RunState.QUEUED, to_state=RunState.RUNNING)
    repository.finalize(
        "run-done",
        from_state=RunState.RUNNING,
        state=RunState.SUCCEEDED,
        reason="complete",
        receipt={"ok": True},
    )
    queue.enqueue("run-done")
    reconciler = RunReconciler(repository, queue, audit, clock=clock)

    events = reconciler.reconcile_once()
    assert "run-done" not in queue.active_run_ids()
    assert events[0].kind == "terminal_queue_drop"


def test_terminal_receipt_race_records_audit_and_does_not_overwrite() -> None:
    runtime, repository, queue, registry, _clock, audit = _stack(max_attempts=3)
    repository.create_or_get(
        RunRecord("run-race", "agent:a", "k5", {}, "managed-cpu", job={"kind": "ok"})
    )
    runtime._worker.enqueue("run-race")
    registry.register("ok", lambda _record: {"artifact_id": "a1"})

    lease = runtime._worker.claim("test-worker")
    assert lease is not None
    repository.finalize(
        "run-race",
        from_state=RunState.RUNNING,
        state=RunState.SUCCEEDED,
        reason="complete",
        receipt={"artifact_id": "winner"},
    )
    # Simulate the late worker attempting to seal again through succeed().
    try:
        runtime._worker.succeed(lease, receipt={"artifact_id": "loser"})
    except RunConflictError:
        runtime._reconciler.record_seal_race(
            lease, detail="terminal_receipt_conflict", terminal_state="succeeded"
        )
        queue.drop("run-race")

    run = repository.get("run-race")
    assert run is not None
    assert run.terminal_receipt == {"artifact_id": "winner"}
    assert audit.counts_by_kind()["seal_race"] == 1
    assert "run-race" not in queue.active_run_ids()


def test_killed_worker_path_converges_via_process_once() -> None:
    runtime, repository, _queue, registry, clock, audit = _stack(max_attempts=1)
    repository.create_or_get(
        RunRecord("run-kill", "agent:a", "k6", {}, "managed-cpu", job={"kind": "work"})
    )
    runtime._worker.enqueue("run-kill")
    lease = runtime._worker.claim("test-worker")
    assert lease is not None
    clock.advance(5)
    registry.register("work", lambda _record: {"ok": True})

    assert runtime.process_once() is False
    run = repository.get("run-kill")
    assert run is not None and run.state is RunState.FAILED
    assert run.terminal_reason == "lease_expired_attempt_limit"
    assert audit.counts_by_kind().get("dead_letter_sealed") == 1