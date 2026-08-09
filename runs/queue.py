"""Lease-based queue contract for managed Star workers.

The queue holds delivery work only; the ``runs`` repository remains the source
of truth for the externally visible lifecycle and sealed receipts.  A lease
token makes acknowledgements and heartbeats safe when a worker is replaced.
"""

from __future__ import annotations

import json
import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar, Protocol

from .domain import RunRecord, RunState


@dataclass(frozen=True)
class QueueLease:
    run_id: str
    attempt: int
    token: str
    expires_at: datetime


@dataclass(frozen=True)
class FailureDisposition:
    retried: bool
    dead_lettered: bool
    reason: str


class QueueBackend(Protocol):
    """Atomic durable queue operations, implemented by Redis or a test fake."""

    def enqueue(self, run_id: str) -> None: ...
    def claim(
        self, worker_id: str, *, lease_for: timedelta, max_attempts: int
    ) -> QueueLease | None: ...
    def heartbeat(self, lease: QueueLease, *, lease_for: timedelta) -> bool: ...
    def acknowledge(self, lease: QueueLease) -> bool: ...
    def fail(
        self, lease: QueueLease, *, reason: str, retry_after: timedelta, max_attempts: int
    ) -> FailureDisposition: ...
    def recover_expired(self, *, max_attempts: int) -> int: ...
    def dead_letters(self) -> tuple[Mapping[str, Any], ...]: ...


class InMemoryQueueBackend:
    """Reference backend.  Its semantics are intentionally Redis-compatible."""

    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._jobs: dict[str, dict[str, Any]] = {}
        self._dead: list[dict[str, Any]] = []

    def enqueue(self, run_id: str) -> None:
        self._jobs.setdefault(
            run_id, {"run_id": run_id, "attempts": 0, "available_at": self._clock()}
        )

    def claim(
        self, worker_id: str, *, lease_for: timedelta, max_attempts: int
    ) -> QueueLease | None:
        self.recover_expired(max_attempts=max_attempts)
        now = self._clock()
        ready = sorted(
            (
                job
                for job in self._jobs.values()
                if job.get("available_at") <= now and "token" not in job
            ),
            key=lambda job: (job["available_at"], job["run_id"]),
        )
        if not ready:
            return None
        job = ready[0]
        if job["attempts"] >= max_attempts:
            self._dead_letter(job, "attempt_limit_exhausted")
            return self.claim(worker_id, lease_for=lease_for, max_attempts=max_attempts)
        job["attempts"] += 1
        token = secrets.token_urlsafe(18)
        expires_at = now + lease_for
        job.update(worker_id=worker_id, token=token, expires_at=expires_at)
        return QueueLease(job["run_id"], job["attempts"], token, expires_at)

    def heartbeat(self, lease: QueueLease, *, lease_for: timedelta) -> bool:
        job = self._valid_job(lease)
        if job is None:
            return False
        job["expires_at"] = self._clock() + lease_for
        return True

    def acknowledge(self, lease: QueueLease) -> bool:
        job = self._valid_job(lease)
        if job is None:
            return False
        del self._jobs[lease.run_id]
        return True

    def fail(
        self, lease: QueueLease, *, reason: str, retry_after: timedelta, max_attempts: int
    ) -> FailureDisposition:
        job = self._valid_job(lease)
        if job is None:
            return FailureDisposition(False, False, "lease_lost")
        if job["attempts"] >= max_attempts:
            self._dead_letter(job, reason)
            return FailureDisposition(False, True, reason)
        job.update(last_reason=reason, available_at=self._clock() + retry_after)
        job.pop("token", None)
        job.pop("expires_at", None)
        job.pop("worker_id", None)
        return FailureDisposition(True, False, reason)

    def recover_expired(self, *, max_attempts: int) -> int:
        now = self._clock()
        recovered = 0
        for job in list(self._jobs.values()):
            if job.get("expires_at") is not None and job["expires_at"] <= now:
                job.update(last_reason="lease_expired", available_at=now)
                job.pop("token", None)
                job.pop("expires_at", None)
                job.pop("worker_id", None)
                recovered += 1
        return recovered

    def dead_letters(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(dict(job) for job in self._dead)

    def _valid_job(self, lease: QueueLease) -> dict[str, Any] | None:
        job = self._jobs.get(lease.run_id)
        if job is None or job.get("token") != lease.token or job.get("expires_at") <= self._clock():
            return None
        return job

    def _dead_letter(self, job: dict[str, Any], reason: str) -> None:
        payload = dict(job, terminal_reason=reason, dead_lettered_at=self._clock())
        payload.pop("token", None)
        payload.pop("expires_at", None)
        payload.pop("worker_id", None)
        self._dead.append(payload)
        del self._jobs[job["run_id"]]


class RedisClient(Protocol):
    """Small subset shared by redis-py and an intentionally tiny test fake."""

    def eval(self, script: str, numkeys: int, *keys_and_args: str) -> str | bytes | None: ...


class RedisQueueBackend:
    """Redis Lua adapter with atomic claim/lease ownership operations.

    The scripts live at this boundary so workers never rely on a non-atomic
    pop-then-lock sequence.  Redis persistence/HA remains a deployment choice.
    """

    _SCRIPTS: ClassVar[dict[str, str]] = {
        "enqueue": """
            local existing = redis.call('HGET', KEYS[1], ARGV[1])
            if existing then return '0' end
            redis.call('HSET', KEYS[1], ARGV[1],
              cjson.encode({run_id=ARGV[1], attempts=0, available_at_ms=tonumber(ARGV[2])}))
            redis.call('ZADD', KEYS[2], ARGV[2], ARGV[1])
            return '1'
        """,
        "claim": """
            while true do
              local ids = redis.call('ZRANGEBYSCORE', KEYS[2], '-inf', ARGV[1], 'LIMIT', 0, 1)
              if #ids == 0 then return nil end
              local run_id = ids[1]
              redis.call('ZREM', KEYS[2], run_id)
              local encoded = redis.call('HGET', KEYS[1], run_id)
              if encoded then
                local job = cjson.decode(encoded)
                if job.attempts >= tonumber(ARGV[3]) then
                  job.terminal_reason = 'attempt_limit_exhausted'
                  job.dead_lettered_at_ms = tonumber(ARGV[1])
                  redis.call('LPUSH', KEYS[4], cjson.encode(job))
                  redis.call('HDEL', KEYS[1], run_id)
                else
                  job.attempts = job.attempts + 1
                  job.worker_id = ARGV[4]
                  job.token = ARGV[5]
                  job.expires_at_ms = tonumber(ARGV[1]) + tonumber(ARGV[2])
                  redis.call('HSET', KEYS[1], run_id, cjson.encode(job))
                  redis.call('ZADD', KEYS[3], job.expires_at_ms, run_id)
                  return cjson.encode({run_id=run_id, attempt=job.attempts,
                    token=job.token, expires_at_ms=job.expires_at_ms})
                end
              end
            end
        """,
        "heartbeat": """
            local encoded = redis.call('HGET', KEYS[1], ARGV[1])
            if not encoded then return '0' end
            local job = cjson.decode(encoded)
            if job.token ~= ARGV[2] or job.expires_at_ms <= tonumber(ARGV[3]) then return '0' end
            job.expires_at_ms = tonumber(ARGV[3]) + tonumber(ARGV[4])
            redis.call('HSET', KEYS[1], ARGV[1], cjson.encode(job))
            redis.call('ZADD', KEYS[2], job.expires_at_ms, ARGV[1])
            return '1'
        """,
        "ack": """
            local encoded = redis.call('HGET', KEYS[1], ARGV[1])
            if not encoded then return '0' end
            local job = cjson.decode(encoded)
            if job.token ~= ARGV[2] or job.expires_at_ms <= tonumber(ARGV[3]) then return '0' end
            redis.call('HDEL', KEYS[1], ARGV[1])
            redis.call('ZREM', KEYS[2], ARGV[1])
            return '1'
        """,
        "fail": """
            local encoded = redis.call('HGET', KEYS[1], ARGV[1])
            if not encoded then
              return cjson.encode({retried=false, dead_lettered=false, reason='lease_lost'})
            end
            local job = cjson.decode(encoded)
            if job.token ~= ARGV[2] or job.expires_at_ms <= tonumber(ARGV[3]) then
              return cjson.encode({retried=false, dead_lettered=false, reason='lease_lost'})
            end
            redis.call('ZREM', KEYS[3], ARGV[1])
            if job.attempts >= tonumber(ARGV[5]) then
              job.terminal_reason = ARGV[6]
              job.dead_lettered_at_ms = tonumber(ARGV[3])
              job.token, job.worker_id, job.expires_at_ms = nil, nil, nil
              redis.call('LPUSH', KEYS[4], cjson.encode(job))
              redis.call('HDEL', KEYS[1], ARGV[1])
              return cjson.encode({retried=false, dead_lettered=true, reason=ARGV[6]})
            end
            job.last_reason = ARGV[6]
            job.available_at_ms = tonumber(ARGV[3]) + tonumber(ARGV[4])
            job.token, job.worker_id, job.expires_at_ms = nil, nil, nil
            redis.call('HSET', KEYS[1], ARGV[1], cjson.encode(job))
            redis.call('ZADD', KEYS[2], job.available_at_ms, ARGV[1])
            return cjson.encode({retried=true, dead_lettered=false, reason=ARGV[6]})
        """,
        "recover": """
            local expired = redis.call('ZRANGEBYSCORE', KEYS[3], '-inf', ARGV[1])
            for _, run_id in ipairs(expired) do
              redis.call('ZREM', KEYS[3], run_id)
              local encoded = redis.call('HGET', KEYS[1], run_id)
              if encoded then
                local job = cjson.decode(encoded)
                job.last_reason = 'lease_expired'
                job.available_at_ms = tonumber(ARGV[1])
                job.token, job.worker_id, job.expires_at_ms = nil, nil, nil
                redis.call('HSET', KEYS[1], run_id, cjson.encode(job))
                redis.call('ZADD', KEYS[2], job.available_at_ms, run_id)
              end
            end
            return tostring(#expired)
        """,
        "dead": """
            local values = redis.call('LRANGE', KEYS[1], 0, -1)
            local decoded = {}
            for i, value in ipairs(values) do decoded[i] = cjson.decode(value) end
            return cjson.encode(decoded)
        """,
    }

    def __init__(
        self,
        client: RedisClient,
        *,
        namespace: str = "orrery:runs",
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._client = client
        self._ns = namespace.rstrip(":")
        self._clock = clock or (lambda: datetime.now(UTC))

    def enqueue(self, run_id: str) -> None:
        self._call(
            "enqueue", [self._key("jobs"), self._key("ready")], [run_id, str(self._millis())]
        )

    def claim(
        self, worker_id: str, *, lease_for: timedelta, max_attempts: int
    ) -> QueueLease | None:
        value = self._call(
            "claim",
            [self._key("jobs"), self._key("ready"), self._key("leases"), self._key("dead")],
            [
                str(self._millis()),
                str(int(lease_for.total_seconds() * 1000)),
                str(max_attempts),
                worker_id,
                secrets.token_urlsafe(18),
            ],
        )
        return self._lease(value)

    def heartbeat(self, lease: QueueLease, *, lease_for: timedelta) -> bool:
        return (
            self._call(
                "heartbeat",
                [self._key("jobs"), self._key("leases")],
                [
                    lease.run_id,
                    lease.token,
                    str(self._millis()),
                    str(int(lease_for.total_seconds() * 1000)),
                ],
            )
            == "1"
        )

    def acknowledge(self, lease: QueueLease) -> bool:
        return (
            self._call(
                "ack",
                [self._key("jobs"), self._key("leases")],
                [lease.run_id, lease.token, str(self._millis())],
            )
            == "1"
        )

    def fail(
        self, lease: QueueLease, *, reason: str, retry_after: timedelta, max_attempts: int
    ) -> FailureDisposition:
        value = self._call(
            "fail",
            [self._key("jobs"), self._key("ready"), self._key("leases"), self._key("dead")],
            [
                lease.run_id,
                lease.token,
                str(self._millis()),
                str(int(retry_after.total_seconds() * 1000)),
                str(max_attempts),
                reason,
            ],
        )
        return FailureDisposition(
            **json.loads(value or '{"retried":false,"dead_lettered":false,"reason":"lease_lost"}')
        )

    def recover_expired(self, *, max_attempts: int) -> int:
        return int(
            self._call(
                "recover",
                [self._key("jobs"), self._key("ready"), self._key("leases")],
                [str(self._millis()), str(max_attempts)],
            )
            or 0
        )

    def dead_letters(self) -> tuple[Mapping[str, Any], ...]:
        raw = self._call("dead", [self._key("dead")], []) or "[]"
        return tuple(json.loads(raw))

    def _key(self, suffix: str) -> str:
        return f"{self._ns}:{suffix}"

    def _millis(self) -> int:
        return int(self._clock().timestamp() * 1000)

    def _call(self, operation: str, keys: list[str], args: list[str]) -> str | None:
        result = self._client.eval(self._SCRIPTS[operation], len(keys), *keys, *args)
        return result.decode() if isinstance(result, bytes) else result

    @staticmethod
    def _lease(value: str | None) -> QueueLease | None:
        if value is None:
            return None
        raw = json.loads(value)
        return QueueLease(
            raw["run_id"],
            raw["attempt"],
            raw["token"],
            datetime.fromtimestamp(raw["expires_at_ms"] / 1000, UTC),
        )


class ManagedRunWorker:
    """Coordinates queue leases with guarded run state transitions."""

    def __init__(
        self,
        runs: Any,
        queue: QueueBackend,
        *,
        max_attempts: int = 3,
        lease_for: timedelta = timedelta(minutes=2),
        retry_after: timedelta = timedelta(seconds=5),
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self.runs, self.queue = runs, queue
        self.max_attempts, self.lease_for, self.retry_after = max_attempts, lease_for, retry_after

    def enqueue(self, run_id: str) -> RunRecord | None:
        record = self.runs.get(run_id)
        if record is None or record.is_terminal:
            return None
        if record.state is RunState.ACCEPTED:
            record = self.runs.transition(
                run_id, from_state=RunState.ACCEPTED, to_state=RunState.QUEUED
            )
            if record is None:
                return None
        self.queue.enqueue(run_id)
        return record

    def claim(self, worker_id: str) -> QueueLease | None:
        lease = self.queue.claim(
            worker_id, lease_for=self.lease_for, max_attempts=self.max_attempts
        )
        if lease is None:
            return None
        record = self.runs.get(lease.run_id)
        if record is None or record.is_terminal:
            self.queue.acknowledge(lease)
            return None
        if record.state is RunState.QUEUED and (
            self.runs.transition(
                lease.run_id, from_state=RunState.QUEUED, to_state=RunState.RUNNING
            )
            is None
        ):
            self.queue.fail(
                lease,
                reason="run_state_race",
                retry_after=self.retry_after,
                max_attempts=self.max_attempts,
            )
            return None
        return lease

    def heartbeat(self, lease: QueueLease) -> bool:
        return self.queue.heartbeat(lease, lease_for=self.lease_for)

    def succeed(self, lease: QueueLease, *, receipt: Mapping[str, Any]) -> bool:
        finalized = self.runs.finalize(
            lease.run_id,
            from_state=RunState.RUNNING,
            state=RunState.SUCCEEDED,
            reason="complete",
            receipt=receipt,
        )
        return finalized is not None and self.queue.acknowledge(lease)

    def fail(self, lease: QueueLease, *, reason: str) -> FailureDisposition:
        disposition = self.queue.fail(
            lease, reason=reason, retry_after=self.retry_after, max_attempts=self.max_attempts
        )
        if disposition.dead_lettered:
            self.runs.finalize(
                lease.run_id,
                from_state=RunState.RUNNING,
                state=RunState.FAILED,
                reason=reason,
                receipt={"kind": "dead_letter", "attempt": lease.attempt},
            )
        return disposition
