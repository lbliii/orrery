"""MCP-facing control/result boundary for managed Star jobs; never executes work."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from runs import ManagedRunSubmission, ManagedRunWorker, PostgresRunRepository, RedisQueueBackend
from runs.admission import RunAdmissionError


class ManagedServiceUnavailable(RuntimeError):
    pass


class ManagedAdmissionRejected(ValueError):
    """Safe caller-facing admission rejection without cross-tenant details."""

    def __init__(self, *, code: str, policy: Mapping[str, object]) -> None:
        self.code = code
        self.policy = dict(policy)
        super().__init__(code)


class ManagedStarService:
    def __init__(self, submission: ManagedRunSubmission, runs: Any, *, worker: Any | None = None) -> None:
        self._submission = submission
        self._runs = runs
        self._worker = worker or submission._worker  # noqa: SLF001 — test seam

    def submit(
        self,
        *,
        kind: str,
        input: Mapping[str, Any],
        idempotency_key: str,
        caller_id: str = "mcp",
    ) -> dict[str, object]:
        try:
            run = self._submission.submit(
                caller_id=caller_id,
                idempotency_key=idempotency_key,
                kind=kind,
                input=input,
            )
        except RunAdmissionError as error:
            raise ManagedAdmissionRejected(code=error.code, policy=error.policy) from error
        return {
            "run_id": run.run_id,
            "state": run.state.value,
            "executor": run.executor,
            "budget": dict(run.budget),
        }

    def cancel(self, *, run_id: str, caller_id: str) -> dict[str, object]:
        record = self._worker.cancel(
            run_id,
            caller_id=caller_id,
            reason="caller_cancelled",
            receipt={"kind": "cancel", "code": "caller_cancelled"},
        )
        if record is None:
            raise ValueError("run not found")
        return {"run_id": record.run_id, "state": record.state.value}

    def result(self, run_id: str) -> dict[str, object]:
        run = self._runs.get(run_id)
        if run is None:
            raise ValueError("run not found")
        payload: dict[str, object] = {"run_id": run.run_id, "state": run.state.value}
        if run.is_terminal:
            # Chirp seals this final-receipt payload in an Ed25519 Envelope.
            payload["receipt"] = dict(run.terminal_receipt or {})
            payload["terminal_reason"] = run.terminal_reason or ""
        return payload


def configured_managed_service() -> ManagedStarService:
    database_url, redis_url = os.environ.get("DATABASE_URL", ""), os.environ.get("REDIS_URL", "")
    if not database_url or not redis_url:
        raise ManagedServiceUnavailable("managed runs require DATABASE_URL and REDIS_URL")
    import psycopg
    import redis

    repository = PostgresRunRepository(lambda: psycopg.connect(database_url))
    repository.initialize()
    worker = ManagedRunWorker(
        repository,
        RedisQueueBackend(redis.Redis.from_url(redis_url)),
    )
    return ManagedStarService(ManagedRunSubmission(worker), repository, worker=worker)
