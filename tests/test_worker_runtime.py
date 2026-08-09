"""Focused coverage for the separately-deployed managed-run worker (#132)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from artifacts.cleanup import CleanupResult
from runs import (
    InMemoryQueueBackend,
    InMemoryRunRepository,
    JobHandlerRegistry,
    ManagedRunWorker,
    RunRecord,
    RunState,
    RunWorkerRuntime,
    WorkerConfigurationError,
    WorkerSettings,
)
from runs.worker import _build_artifact_cleanup


def _runtime(
    job: dict[str, object] | None, *, max_attempts: int = 3
) -> tuple[RunWorkerRuntime, InMemoryRunRepository, InMemoryQueueBackend, JobHandlerRegistry]:
    repository = InMemoryRunRepository(clock=lambda: datetime(2026, 8, 9, tzinfo=UTC))
    repository.create_or_get(RunRecord("run-1", "agent:a", "request-1", {}, "managed-cpu", job=job))
    queue = InMemoryQueueBackend(clock=lambda: datetime(2026, 8, 9, tzinfo=UTC))
    worker = ManagedRunWorker(
        repository,
        queue,
        max_attempts=max_attempts,
        lease_for=timedelta(seconds=3),
        retry_after=timedelta(0),
    )
    worker.enqueue("run-1")
    settings = WorkerSettings(
        "postgres://example",
        "redis://example",
        "test-worker",
        max_attempts=max_attempts,
        lease_seconds=3,
    )
    registry = JobHandlerRegistry()
    return RunWorkerRuntime(worker, registry, settings), repository, queue, registry


def test_separate_runtime_claims_and_executes_only_registered_serialized_job() -> None:
    runtime, repository, queue, registry = _runtime({"kind": "csv-export", "input": {"id": 1}})
    received: list[RunRecord] = []
    registry.register(
        "csv-export", lambda record: received.append(record) or {"artifact_id": "art-1"}
    )

    assert runtime.process_once()
    assert received[0].job == {"kind": "csv-export", "input": {"id": 1}}
    assert repository.get("run-1").state is RunState.SUCCEEDED  # type: ignore[union-attr]
    assert not queue.dead_letters()


def test_unknown_or_missing_job_is_explicitly_dead_lettered_not_executed() -> None:
    runtime, repository, queue, _ = _runtime({"kind": "never-installed"})

    assert runtime.process_once()
    run = repository.get("run-1")
    assert run is not None and run.state is RunState.FAILED
    assert run.terminal_reason == "unknown_job_kind:never-installed"
    assert queue.dead_letters()[0]["terminal_reason"] == "unknown_job_kind:never-installed"


def test_handler_exception_uses_bounded_retry_then_dead_letters() -> None:
    runtime, repository, queue, registry = _runtime({"kind": "explode"}, max_attempts=1)
    registry.register("explode", lambda _record: (_ for _ in ()).throw(RuntimeError("boom")))

    assert runtime.process_once()
    run = repository.get("run-1")
    assert run is not None and run.state is RunState.FAILED
    assert run.terminal_reason == "handler_error"
    assert queue.dead_letters()[0]["terminal_reason"] == "handler_error"


def test_final_expired_lease_is_dead_lettered_and_seals_postgres_run_failure() -> None:
    class Clock:
        now = datetime(2026, 8, 9, tzinfo=UTC)

        def __call__(self) -> datetime:
            return self.now

    clock = Clock()
    repository = InMemoryRunRepository(clock=clock)
    repository.create_or_get(
        RunRecord("run-1", "agent:a", "request-1", {}, "managed-cpu", job={"kind": "ok"})
    )
    queue = InMemoryQueueBackend(clock=clock)
    worker = ManagedRunWorker(
        repository,
        queue,
        max_attempts=1,
        lease_for=timedelta(seconds=3),
        retry_after=timedelta(0),
    )
    worker.enqueue("run-1")
    assert worker.claim("crashed-worker") is not None
    clock.now += timedelta(seconds=4)
    runtime = RunWorkerRuntime(
        worker,
        JobHandlerRegistry(),
        WorkerSettings("postgres://example", "redis://example", "recovery", max_attempts=1),
    )

    assert not runtime.process_once()
    run = repository.get("run-1")
    assert run is not None and run.state is RunState.FAILED
    assert run.terminal_reason == "lease_expired_attempt_limit"
    assert queue.dead_letters()[0]["terminal_reason"] == "lease_expired_attempt_limit"


def test_settings_require_both_durable_backends_and_safe_values() -> None:
    with pytest.raises(WorkerConfigurationError, match="DATABASE_URL"):
        WorkerSettings.from_env({"REDIS_URL": "redis://example"})
    with pytest.raises(WorkerConfigurationError, match="safe bounds"):
        WorkerSettings.from_env(
            {
                "DATABASE_URL": "postgres://example",
                "REDIS_URL": "redis://example",
                "ORRERY_WORKER_LEASE_SECONDS": "2",
            }
        )

    settings = WorkerSettings.from_env(
        {"DATABASE_URL": "postgres://example", "REDIS_URL": "redis://example"}
    )
    assert settings.worker_id


def test_durable_artifact_cleanup_requires_bucket_and_wires_s3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = WorkerSettings("postgres://example", "redis://example", "worker")
    monkeypatch.setenv("ORRERY_ARTIFACT_BACKEND", "railway-bucket")
    monkeypatch.delenv("ORRERY_ARTIFACT_BUCKET", raising=False)
    with pytest.raises(WorkerConfigurationError, match="ORRERY_ARTIFACT_BUCKET"):
        _build_artifact_cleanup(settings, _FakePsycopg())

    monkeypatch.setenv("ORRERY_ARTIFACT_BUCKET", "orrery-artifacts")
    monkeypatch.setitem(__import__("sys").modules, "boto3", _FakeBoto3())
    cleanup = _build_artifact_cleanup(settings, _FakePsycopg())
    assert cleanup is not None


def test_runtime_runs_bounded_cleanup_on_startup_and_interval() -> None:
    runtime, _, _, _ = _runtime(None)
    clock = _MonotonicClock()
    cleanup = _Cleanup()
    runtime._artifact_cleanup = cleanup
    runtime._monotonic = clock

    runtime.process_once()
    clock.now = 299
    runtime.process_once()
    clock.now = 300
    runtime.process_once()

    assert cleanup.batch_sizes == [100, 100]


class _FakePsycopg:
    @staticmethod
    def connect(_url: str) -> object:
        return _SchemaConnection()


class _FakeBoto3:
    @staticmethod
    def client(_kind: str, **_kwargs: object) -> object:
        return object()


class _MonotonicClock:
    now = 0.0

    def __call__(self) -> float:
        return self.now


class _Cleanup:
    def __init__(self) -> None:
        self.batch_sizes: list[int] = []

    def cleanup_once(self, *, batch_size: int = 100) -> CleanupResult:
        self.batch_sizes.append(batch_size)
        return CleanupResult()


class _SchemaCursor:
    def execute(self, *_args: object) -> None:
        pass

    def close(self) -> None:
        pass


class _SchemaConnection:
    def cursor(self) -> _SchemaCursor:
        return _SchemaCursor()

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        pass
