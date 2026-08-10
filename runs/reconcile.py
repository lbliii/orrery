"""Cross-store reconciliation and compact audit for managed runs (#158).

Postgres remains the sealed-receipt authority. Redis owns delivery leases. When
those pictures diverge, this module converges them without overwriting a sealed
receipt and records a compact audit explanation operators can read.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, MutableSequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from .domain import RunConflictError, RunRecord, RunState
from .queue import QueueBackend, QueueLease


@dataclass(frozen=True)
class AuditEvent:
    """One compact explanation of a reconcile or attempt transition."""

    kind: str
    run_id: str
    reason: str
    evidence: Mapping[str, Any]
    at: datetime

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "run_id": self.run_id,
            "reason": self.reason,
            "evidence": dict(self.evidence),
            "at": self.at.isoformat().replace("+00:00", "Z"),
        }


class AuditLog(Protocol):
    def append(self, event: AuditEvent) -> None: ...
    def list(self, *, limit: int = 100) -> tuple[AuditEvent, ...]: ...
    def counts_by_kind(self) -> Mapping[str, int]: ...


class InMemoryAuditLog:
    """Deterministic audit store for tests and single-worker processes."""

    def __init__(self, *, limit: int = 1000) -> None:
        self._limit = limit
        self._events: MutableSequence[AuditEvent] = []

    def append(self, event: AuditEvent) -> None:
        self._events.append(event)
        overflow = len(self._events) - self._limit
        if overflow > 0:
            del self._events[0:overflow]

    def list(self, *, limit: int = 100) -> tuple[AuditEvent, ...]:
        if limit < 1:
            return ()
        return tuple(self._events[-limit:])

    def counts_by_kind(self) -> Mapping[str, int]:
        return dict(Counter(event.kind for event in self._events))


class RunRepositoryView(Protocol):
    def get(self, run_id: str) -> RunRecord | None: ...
    def list_by_states(self, *states: RunState) -> tuple[RunRecord, ...]: ...
    def finalize(
        self,
        run_id: str,
        *,
        from_state: RunState,
        state: RunState,
        reason: str,
        receipt: Mapping[str, Any],
    ) -> RunRecord | None: ...


class ReconcilableQueue(QueueBackend, Protocol):
    def active_run_ids(self) -> frozenset[str]: ...
    def drop(self, run_id: str) -> bool: ...


@dataclass
class RunReconciler:
    """Deterministic repairs for killed workers, lease expiry, and divergence."""

    runs: RunRepositoryView
    queue: ReconcilableQueue
    audit: AuditLog
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def reconcile_once(self) -> tuple[AuditEvent, ...]:
        events: list[AuditEvent] = []
        events.extend(self._seal_dead_letters())
        events.extend(self._drop_queue_for_terminal_runs())
        events.extend(self._repair_orphans())
        return tuple(events)

    def record_attempt(
        self,
        lease: QueueLease,
        *,
        worker_id: str,
        queue_age_seconds: float | None = None,
    ) -> AuditEvent:
        event = self._event(
            "attempt",
            lease.run_id,
            "claimed",
            {
                "worker_id": worker_id,
                "attempt": lease.attempt,
                "lease_token": lease.token,
                "lease_expires_at": lease.expires_at.isoformat().replace("+00:00", "Z"),
                "queue_age_seconds": queue_age_seconds,
            },
        )
        self.audit.append(event)
        return event

    def record_lease_loss(self, lease: QueueLease, *, worker_id: str) -> AuditEvent:
        event = self._event(
            "lease_loss",
            lease.run_id,
            "lease_lost",
            {"worker_id": worker_id, "attempt": lease.attempt, "lease_token": lease.token},
        )
        self.audit.append(event)
        return event

    def record_seal_race(
        self, lease: QueueLease, *, detail: str, terminal_state: str | None = None
    ) -> AuditEvent:
        event = self._event(
            "seal_race",
            lease.run_id,
            detail,
            {
                "attempt": lease.attempt,
                "lease_token": lease.token,
                "terminal_state": terminal_state,
            },
        )
        self.audit.append(event)
        return event

    def _seal_dead_letters(self) -> list[AuditEvent]:
        events: list[AuditEvent] = []
        for dead in self.queue.dead_letters():
            run_id, reason = dead.get("run_id"), dead.get("terminal_reason")
            if not isinstance(run_id, str) or not isinstance(reason, str):
                continue
            record = self.runs.get(run_id)
            if record is None:
                continue
            if record.is_terminal:
                if record.state is RunState.FAILED and record.terminal_reason == reason:
                    continue
                events.append(
                    self._emit(
                        "dead_letter_ignored_terminal",
                        run_id,
                        "postgres_already_terminal",
                        {
                            "queue_reason": reason,
                            "postgres_state": record.state.value,
                            "postgres_reason": record.terminal_reason,
                        },
                    )
                )
                continue
            if record.state is not RunState.RUNNING:
                continue
            try:
                finalized = self.runs.finalize(
                    run_id,
                    from_state=RunState.RUNNING,
                    state=RunState.FAILED,
                    reason=reason,
                    receipt={
                        "kind": "dead_letter",
                        "attempt": dead.get("attempts"),
                        "reconciled": True,
                    },
                )
            except RunConflictError:
                existing = self.runs.get(run_id)
                events.append(
                    self._emit(
                        "seal_race",
                        run_id,
                        "terminal_receipt_conflict",
                        {
                            "queue_reason": reason,
                            "postgres_state": None if existing is None else existing.state.value,
                        },
                    )
                )
                continue
            if finalized is not None:
                events.append(
                    self._emit(
                        "dead_letter_sealed",
                        run_id,
                        reason,
                        {"attempt": dead.get("attempts"), "from": "running", "to": "failed"},
                    )
                )
        return events

    def _drop_queue_for_terminal_runs(self) -> list[AuditEvent]:
        events: list[AuditEvent] = []
        for run_id in sorted(self.queue.active_run_ids()):
            record = self.runs.get(run_id)
            if record is None or not record.is_terminal:
                continue
            if self.queue.drop(run_id):
                events.append(
                    self._emit(
                        "terminal_queue_drop",
                        run_id,
                        "postgres_terminal_queue_stale",
                        {
                            "postgres_state": record.state.value,
                            "postgres_reason": record.terminal_reason,
                        },
                    )
                )
        return events

    def _repair_orphans(self) -> list[AuditEvent]:
        events: list[AuditEvent] = []
        active = self.queue.active_run_ids()
        dead_ids = {
            dead["run_id"]
            for dead in self.queue.dead_letters()
            if isinstance(dead.get("run_id"), str)
        }
        for record in self.runs.list_by_states(RunState.QUEUED, RunState.RUNNING):
            if record.run_id in active or record.run_id in dead_ids:
                continue
            if record.state is RunState.QUEUED:
                self.queue.enqueue(record.run_id)
                events.append(
                    self._emit(
                        "orphan_requeued",
                        record.run_id,
                        "queued_missing_from_queue",
                        {"from": "queued", "to": "queued"},
                    )
                )
                continue
            finalized = self.runs.finalize(
                record.run_id,
                from_state=RunState.RUNNING,
                state=RunState.FAILED,
                reason="orphaned_running",
                receipt={"kind": "reconcile", "detail": "running_missing_from_queue"},
            )
            if finalized is not None:
                events.append(
                    self._emit(
                        "orphan_sealed",
                        record.run_id,
                        "orphaned_running",
                        {"from": "running", "to": "failed"},
                    )
                )
        return events

    def _emit(
        self, kind: str, run_id: str, reason: str, evidence: Mapping[str, Any]
    ) -> AuditEvent:
        event = self._event(kind, run_id, reason, evidence)
        self.audit.append(event)
        return event

    def _event(
        self, kind: str, run_id: str, reason: str, evidence: Mapping[str, Any]
    ) -> AuditEvent:
        return AuditEvent(
            kind=kind,
            run_id=run_id,
            reason=reason,
            evidence=dict(evidence),
            at=self.clock(),
        )
