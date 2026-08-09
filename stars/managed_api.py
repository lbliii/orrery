"""MCP-facing control/result boundary for managed Star jobs; never executes work."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from runs import ManagedRunSubmission, ManagedRunWorker, PostgresRunRepository, RedisQueueBackend


class ManagedServiceUnavailable(RuntimeError):
    pass


class ManagedStarService:
    def __init__(self, submission: ManagedRunSubmission, runs: Any) -> None:
        self._submission, self._runs = submission, runs

    def submit(
        self, *, kind: str, input: Mapping[str, Any], idempotency_key: str
    ) -> dict[str, object]:
        run = self._submission.submit(
            caller_id="mcp", idempotency_key=idempotency_key, kind=kind, input=input
        )
        return {"run_id": run.run_id, "state": run.state.value, "executor": run.executor}

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
    return ManagedStarService(ManagedRunSubmission(worker), repository)
