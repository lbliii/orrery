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


@dataclass(frozen=True)
class QueueStats:
    ready_depth: int
    leased_depth: int
    dead_letter_depth: int
    oldest_ready_age_seconds: float | None
    oldest_lease_age_seconds: float | None


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
    def active_run_ids(self) -> frozenset[str]: ...
    def drop(self, run_id: str) -> bool: ...
    def stats(self) -> QueueStats: ...


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
                if job["attempts"] >= max_attempts:
                    self._dead_letter(job, "lease_expired_attempt_limit")
                    recovered += 1
                    continue
                job.update(last_reason="lease_expired", available_at=now)
                job.pop("token", None)
                job.pop("expires_at", None)
                job.pop("worker_id", None)
                recovered += 1
        return recovered

    def dead_letters(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(dict(job) for job in self._dead)

    def active_run_ids(self) -> frozenset[str]:
        return frozenset(self._jobs)

    def drop(self, run_id: str) -> bool:
        job = self._jobs.pop(run_id, None)
        return job is not None

    def stats(self) -> QueueStats:
        now = self._clock()
        ready_ages: list[float] = []
        lease_ages: list[float] = []
        ready_depth = leased_depth = 0
        for job in self._jobs.values():
            if "token" in job:
                leased_depth += 1
                expires = job.get("expires_at")
                if isinstance(expires, datetime):
                    # Age of the lease is how long until expiry inverted: seconds held ≈
                    # not tracked; expose seconds until expiry as negative age signal via
                    # oldest lease = max(now - available proxy). Use expires_at - lease
                    # start unknown; report seconds past available_at while leased.
                    available = job.get("available_at")
                    if isinstance(available, datetime):
                        lease_ages.append(max(0.0, (now - available).total_seconds()))
            elif job.get("available_at") <= now:
                ready_depth += 1
                available = job["available_at"]
                ready_ages.append(max(0.0, (now - available).total_seconds()))
            else:
                ready_depth += 1
                available = job["available_at"]
                ready_ages.append(max(0.0, (now - available).total_seconds()))
        return QueueStats(
            ready_depth=ready_depth,
            leased_depth=leased_depth,
            dead_letter_depth=len(self._dead),
            oldest_ready_age_seconds=max(ready_ages) if ready_ages else None,
            oldest_lease_age_seconds=max(lease_ages) if lease_ages else None,
        )

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
    def hkeys(self, name: str) -> list[Any]: ...
    def hdel(self, name: str, *keys: str) -> int: ...
    def zrem(self, name: str, *values: str) -> int: ...
    def hlen(self, name: str) -> int: ...
    def zcard(self, name: str) -> int: ...
    def llen(self, name: str) -> int: ...
    def zrange(self, name: str, start: int, end: int, withscores: bool = False) -> list[Any]: ...


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
                if job.attempts >= tonumber(ARGV[2]) then
                  job.terminal_reason = 'lease_expired_attempt_limit'
                  job.dead_lettered_at_ms = tonumber(ARGV[1])
                  job.token, job.worker_id, job.expires_at_ms = nil, nil, nil
                  redis.call('LPUSH', KEYS[4], cjson.encode(job))
                  redis.call('HDEL', KEYS[1], run_id)
                else
                  job.last_reason = 'lease_expired'
                  job.available_at_ms = tonumber(ARGV[1])
                  job.token, job.worker_id, job.expires_at_ms = nil, nil, nil
                  redis.call('HSET', KEYS[1], run_id, cjson.encode(job))
                  redis.call('ZADD', KEYS[2], job.available_at_ms, run_id)
                end
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
                [self._key("jobs"), self._key("ready"), self._key("leases"), self._key("dead")],
                [str(self._millis()), str(max_attempts)],
            )
            or 0
        )

    def dead_letters(self) -> tuple[Mapping[str, Any], ...]:
        raw = self._call("dead", [self._key("dead")], []) or "[]"
        return tuple(json.loads(raw))

    def active_run_ids(self) -> frozenset[str]:
        keys = self._client.hkeys(self._key("jobs"))
        return frozenset(
            key.decode() if isinstance(key, bytes) else str(key) for key in keys
        )

    def drop(self, run_id: str) -> bool:
        removed = int(self._client.hdel(self._key("jobs"), run_id) or 0)
        self._client.zrem(self._key("ready"), run_id)
        self._client.zrem(self._key("leases"), run_id)
        return removed > 0

    def stats(self) -> QueueStats:
        now_ms = self._millis()
        ready = self._client.zrange(self._key("ready"), 0, -1, withscores=True)
        leases = self._client.zrange(self._key("leases"), 0, -1, withscores=True)
        ready_ages = [
            max(0.0, (now_ms - float(score)) / 1000.0)
            for _member, score in _score_pairs(ready)
        ]
        # Lease zset scores are expiry timestamps; report how overdue the worst
        # lease is (0 while healthy). Full "held for" needs claim-time storage.
        lease_overdue = [
            max(0.0, (now_ms - float(score)) / 1000.0)
            for _member, score in _score_pairs(leases)
        ]
        return QueueStats(
            ready_depth=int(self._client.zcard(self._key("ready")) or 0),
            leased_depth=int(self._client.zcard(self._key("leases")) or 0),
            dead_letter_depth=int(self._client.llen(self._key("dead")) or 0),
            oldest_ready_age_seconds=max(ready_ages) if ready_ages else None,
            oldest_lease_age_seconds=max(lease_overdue) if lease_overdue else None,
        )

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


def _score_pairs(values: list[Any]) -> list[tuple[Any, float]]:
    if not values:
        return []
    if isinstance(values[0], (tuple, list)) and len(values[0]) == 2:
        return [(item[0], float(item[1])) for item in values]
    # Flat [member, score, member, score, ...]
    pairs: list[tuple[Any, float]] = []
    for index in range(0, len(values), 2):
        pairs.append((values[index], float(values[index + 1])))
    return pairs


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
        if finalized is None:
            return False
        return self.queue.acknowledge(lease) or self.queue.drop(lease.run_id)

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
