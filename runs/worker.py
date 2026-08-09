"""The separately deployed, durable worker process for managed Star runs.

This module is intentionally not imported by the web app.  Railway must run
``python -m runs.worker`` in a distinct service with the same DATABASE_URL and
REDIS_URL; a web replica therefore cannot accidentally become a worker just by
handling an MCP request.
"""

from __future__ import annotations

import argparse
import logging
import os
import socket
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Protocol

from .domain import PostgresRunRepository, RunRecord, RunState
from .queue import ManagedRunWorker, QueueLease, RedisQueueBackend

logger = logging.getLogger(__name__)


class WorkerConfigurationError(ValueError):
    """Raised before the worker starts with incomplete/invalid deployment config."""


class UnknownJobError(ValueError):
    """The stored descriptor names no installed worker handler."""


class JobHandler(Protocol):
    """Pure run handler contract for a known serializable job kind."""

    def __call__(self, record: RunRecord) -> Mapping[str, Any]: ...


class JobHandlerRegistry:
    """A closed registry; stored job kinds never resolve via dynamic imports."""

    def __init__(self) -> None:
        self._handlers: dict[str, JobHandler] = {}

    def register(self, kind: str, handler: JobHandler) -> None:
        if not kind or not kind.replace("-", "").replace("_", "").isalnum():
            raise ValueError("job kind must contain letters, digits, '-' or '_'")
        if kind in self._handlers:
            raise ValueError(f"job handler is already registered: {kind}")
        self._handlers[kind] = handler

    def execute(self, record: RunRecord) -> Mapping[str, Any]:
        descriptor = record.job
        kind = descriptor.get("kind") if descriptor is not None else None
        if not isinstance(kind, str) or not kind:
            raise UnknownJobError("missing_job_descriptor")
        handler = self._handlers.get(kind)
        if handler is None:
            raise UnknownJobError(f"unknown_job_kind:{kind}")
        receipt = handler(record)
        if not isinstance(receipt, Mapping):
            raise TypeError(f"job handler {kind!r} returned a non-mapping receipt")
        return dict(receipt)


@dataclass(frozen=True)
class WorkerSettings:
    database_url: str
    redis_url: str
    worker_id: str
    namespace: str = "orrery:runs"
    max_attempts: int = 3
    lease_seconds: int = 120
    retry_seconds: int = 5
    poll_seconds: float = 1.0

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> WorkerSettings:
        values = os.environ if environ is None else environ
        database_url = values.get("DATABASE_URL", "").strip()
        redis_url = values.get("REDIS_URL", "").strip()
        if not database_url:
            raise WorkerConfigurationError("DATABASE_URL is required for the worker")
        if not redis_url:
            raise WorkerConfigurationError("REDIS_URL is required for the worker")
        try:
            max_attempts = int(values.get("ORRERY_WORKER_MAX_ATTEMPTS", "3"))
            lease_seconds = int(values.get("ORRERY_WORKER_LEASE_SECONDS", "120"))
            retry_seconds = int(values.get("ORRERY_WORKER_RETRY_SECONDS", "5"))
            poll_seconds = float(values.get("ORRERY_WORKER_POLL_SECONDS", "1"))
        except ValueError as error:
            raise WorkerConfigurationError("worker timing settings must be numeric") from error
        if max_attempts < 1 or lease_seconds < 3 or retry_seconds < 0 or poll_seconds <= 0:
            raise WorkerConfigurationError("worker settings are outside safe bounds")
        return cls(
            database_url=database_url,
            redis_url=redis_url,
            worker_id=values.get("ORRERY_WORKER_ID", "").strip()
            or f"{socket.gethostname()}:{os.getpid()}",
            namespace=values.get("ORRERY_RUN_QUEUE_NAMESPACE", "orrery:runs").strip()
            or "orrery:runs",
            max_attempts=max_attempts,
            lease_seconds=lease_seconds,
            retry_seconds=retry_seconds,
            poll_seconds=poll_seconds,
        )


class RunWorkerRuntime:
    """Consumes one durable queue at a time with recovery and lease heartbeats."""

    def __init__(
        self, worker: ManagedRunWorker, registry: JobHandlerRegistry, settings: WorkerSettings
    ) -> None:
        self._worker = worker
        self._registry = registry
        self._settings = settings

    def process_once(self) -> bool:
        recovered = self._worker.queue.recover_expired(max_attempts=self._settings.max_attempts)
        if recovered:
            logger.warning("recovered expired run leases", extra={"recovered": recovered})
        self._seal_recovered_dead_letters()
        lease = self._worker.claim(self._settings.worker_id)
        if lease is None:
            return False
        logger.info("claimed run", extra={"run_id": lease.run_id, "attempt": lease.attempt})
        record = self._worker.runs.get(lease.run_id)
        if record is None:
            # Defensive: claim normally detects this, but never execute unknown state.
            self._dead_letter(lease, "run_not_found")
            return True
        return self._execute(lease, record)

    def run_forever(self) -> None:
        logger.info("run worker started", extra={"worker_id": self._settings.worker_id})
        while True:
            worked = self.process_once()
            if not worked:
                time.sleep(self._settings.poll_seconds)

    def _execute(self, lease: QueueLease, record: RunRecord) -> bool:
        stopped = threading.Event()
        lease_lost = threading.Event()
        heartbeat = threading.Thread(
            target=self._heartbeat_loop,
            args=(lease, stopped, lease_lost),
            name=f"run-heartbeat-{lease.run_id}",
            daemon=True,
        )
        heartbeat.start()
        try:
            receipt = self._registry.execute(record)
        except UnknownJobError as error:
            self._dead_letter(lease, str(error))
        except Exception:
            logger.exception(
                "run handler failed", extra={"run_id": lease.run_id, "attempt": lease.attempt}
            )
            if not lease_lost.is_set():
                disposition = self._worker.fail(lease, reason="handler_error")
                logger.warning(
                    "run handler failure recorded",
                    extra={
                        "run_id": lease.run_id,
                        "attempt": lease.attempt,
                        "retried": disposition.retried,
                        "dead_lettered": disposition.dead_lettered,
                    },
                )
        else:
            if lease_lost.is_set():
                logger.warning("run finished after lease loss", extra={"run_id": lease.run_id})
            elif not self._worker.succeed(lease, receipt=receipt):
                logger.warning("could not seal/ack successful run", extra={"run_id": lease.run_id})
            else:
                logger.info(
                    "run succeeded", extra={"run_id": lease.run_id, "attempt": lease.attempt}
                )
        finally:
            stopped.set()
            heartbeat.join(timeout=1)
        return True

    def _heartbeat_loop(
        self, lease: QueueLease, stopped: threading.Event, lease_lost: threading.Event
    ) -> None:
        # Refresh well before expiry, while retaining a lower bound for short test leases.
        every = max(1.0, self._settings.lease_seconds / 3)
        while not stopped.wait(every):
            if not self._worker.heartbeat(lease):
                lease_lost.set()
                logger.error(
                    "run lease lost", extra={"run_id": lease.run_id, "attempt": lease.attempt}
                )
                return

    def _dead_letter(self, lease: QueueLease, reason: str) -> None:
        disposition = self._worker.queue.fail(
            lease,
            reason=reason,
            retry_after=timedelta(0),
            # Setting the limit to this attempt is an intentional immediate
            # dead-letter for a permanently unexecutable descriptor.
            max_attempts=lease.attempt,
        )
        if disposition.dead_lettered:
            self._worker.runs.finalize(
                lease.run_id,
                from_state=RunState.RUNNING,
                state=RunState.FAILED,
                reason=reason,
                receipt={"kind": "dead_letter", "attempt": lease.attempt},
            )
        logger.error(
            "run dead-lettered",
            extra={"run_id": lease.run_id, "attempt": lease.attempt, "reason": reason},
        )

    def _seal_recovered_dead_letters(self) -> None:
        """Bring Postgres current when Redis expires the final worker lease.

        Queue ownership intentionally wins during a crash; this reconciliation
        is idempotent and only seals a still-running record.
        """
        for dead in self._worker.queue.dead_letters():
            run_id, reason = dead.get("run_id"), dead.get("terminal_reason")
            if not isinstance(run_id, str) or not isinstance(reason, str):
                continue
            record = self._worker.runs.get(run_id)
            if record is None or record.state is not RunState.RUNNING:
                continue
            finalized = self._worker.runs.finalize(
                run_id,
                from_state=RunState.RUNNING,
                state=RunState.FAILED,
                reason=reason,
                receipt={"kind": "dead_letter", "attempt": dead.get("attempts")},
            )
            if finalized is not None:
                logger.error(
                    "recovered dead-letter sealed", extra={"run_id": run_id, "reason": reason}
                )


def build_runtime(
    settings: WorkerSettings, registry: JobHandlerRegistry | None = None
) -> RunWorkerRuntime:
    """Wire production adapters.  Handler registration is explicit at deployment."""
    import psycopg
    import redis

    repository = PostgresRunRepository(lambda: psycopg.connect(settings.database_url))
    repository.initialize()
    queue = RedisQueueBackend(
        redis.Redis.from_url(settings.redis_url), namespace=settings.namespace
    )
    worker = ManagedRunWorker(
        repository,
        queue,
        max_attempts=settings.max_attempts,
        lease_for=timedelta(seconds=settings.lease_seconds),
        retry_after=timedelta(seconds=settings.retry_seconds),
    )
    return RunWorkerRuntime(worker, registry or JobHandlerRegistry(), settings)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Orrery's separate managed-run worker")
    parser.add_argument("--once", action="store_true", help="claim and process at most one run")
    args = parser.parse_args(argv)
    logging.basicConfig(level=os.environ.get("ORRERY_WORKER_LOG_LEVEL", "INFO"))
    runtime = build_runtime(WorkerSettings.from_env())
    if args.once:
        return 0 if runtime.process_once() else 1
    runtime.run_forever()
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through module invocation
    raise SystemExit(main())
