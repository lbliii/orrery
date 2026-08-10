"""Acceptance coverage for #132 queue leases, recovery, and dead letters."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from runs import (
    InMemoryQueueBackend,
    InMemoryRunRepository,
    ManagedRunWorker,
    RedisQueueBackend,
    RunRecord,
    RunState,
)


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 8, 9, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, duration: timedelta) -> None:
        self.now += duration


def _worker(
    clock: Clock, *, max_attempts: int = 3
) -> tuple[ManagedRunWorker, InMemoryRunRepository]:
    runs = InMemoryRunRepository(clock=clock)
    runs.create_or_get(RunRecord("run-1", "agent:a", "request-1", {}, "managed-cpu"))
    return (
        ManagedRunWorker(
            runs,
            InMemoryQueueBackend(clock=clock),
            max_attempts=max_attempts,
            lease_for=timedelta(seconds=10),
            retry_after=timedelta(seconds=2),
        ),
        runs,
    )


def test_claim_is_leased_and_a_stale_worker_cannot_acknowledge_or_heartbeat() -> None:
    clock = Clock()
    worker, _ = _worker(clock)
    worker.enqueue("run-1")
    first = worker.claim("worker-a")
    assert first is not None
    assert worker.claim("worker-b") is None

    clock.advance(timedelta(seconds=11))
    assert worker.queue.recover_expired(max_attempts=3) == 1
    second = worker.claim("worker-b")
    assert second is not None and second.token != first.token and second.attempt == 2
    assert not worker.heartbeat(first)
    assert not worker.queue.acknowledge(first)


def test_failures_are_bounded_and_dead_letter_keeps_reason_for_operator_visibility() -> None:
    clock = Clock()
    worker, runs = _worker(clock, max_attempts=2)
    worker.enqueue("run-1")
    first = worker.claim("worker-a")
    assert first is not None
    assert worker.fail(first, reason="renderer_timeout").retried

    clock.advance(timedelta(seconds=2))
    second = worker.claim("worker-b")
    assert second is not None and second.attempt == 2
    disposition = worker.fail(second, reason="renderer_timeout")

    assert disposition.dead_lettered and not disposition.retried
    assert runs.get("run-1").state is RunState.FAILED  # type: ignore[union-attr]
    dead = worker.queue.dead_letters()
    assert dead[0]["terminal_reason"] == "renderer_timeout"
    assert dead[0]["attempts"] == 2


def test_success_seals_run_receipt_then_removes_only_current_lease() -> None:
    clock = Clock()
    worker, runs = _worker(clock)
    worker.enqueue("run-1")
    lease = worker.claim("worker-a")
    assert lease is not None

    assert worker.succeed(lease, receipt={"artifact_id": "art-1"})
    assert runs.get("run-1").state is RunState.SUCCEEDED  # type: ignore[union-attr]
    assert worker.claim("worker-b") is None


def test_redis_adapter_submits_concrete_atomic_lua_and_handles_redis_py_bytes() -> None:
    clock = Clock()
    redis = _FakeRedis(
        [b'{"run_id":"run-1","attempt":1,"token":"token-a","expires_at_ms":1765699210000}']
    )
    backend = RedisQueueBackend(redis, clock=clock)

    lease = backend.claim("worker-a", lease_for=timedelta(seconds=10), max_attempts=3)

    assert lease is not None and lease.token == "token-a"
    script, key_count, payload = redis.calls[0]
    assert "ZRANGEBYSCORE" in script and "ZREM" in script and "HSET" in script
    assert key_count == 4
    assert payload[:4] == (
        "orrery:runs:jobs",
        "orrery:runs:ready",
        "orrery:runs:leases",
        "orrery:runs:dead",
    )
    assert payload[-2:] == ("worker-a", payload[-1])


class _FakeRedis:
    def __init__(self, replies: list[str | bytes | None]) -> None:
        self.replies = replies
        self.calls: list[tuple[str, int, tuple[str, ...]]] = []

    def eval(self, script: str, numkeys: int, *keys_and_args: str) -> str | bytes | None:
        self.calls.append((script, numkeys, keys_and_args))
        return self.replies.pop(0)

    def hkeys(self, _name: str) -> list[str]:
        return []

    def hdel(self, _name: str, *_keys: str) -> int:
        return 0

    def zrem(self, _name: str, *_values: str) -> int:
        return 0

    def hlen(self, _name: str) -> int:
        return 0

    def zcard(self, _name: str) -> int:
        return 0

    def llen(self, _name: str) -> int:
        return 0

    def zrange(self, _name: str, _start: int, _end: int, withscores: bool = False) -> list:
        del withscores
        return []
