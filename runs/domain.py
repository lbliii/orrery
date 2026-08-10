"""Persistence boundary and state machine for asynchronous Star runs.

Runs deliberately outlive the request that accepted them.  The worker/queue
implementation can be swapped later because it only needs these guarded,
serializable lifecycle operations.
"""

from __future__ import annotations

import json
import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol


class RunState(StrEnum):
    ACCEPTED = "accepted"
    QUEUED = "queued"
    RUNNING = "running"
    UPLOADING = "uploading"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


_TERMINAL_STATES = frozenset({RunState.SUCCEEDED, RunState.FAILED, RunState.CANCELLED})
_TRANSITIONS = {
    RunState.ACCEPTED: frozenset({RunState.QUEUED, RunState.CANCELLED}),
    RunState.QUEUED: frozenset({RunState.RUNNING, RunState.CANCELLED}),
    RunState.RUNNING: frozenset(
        {RunState.UPLOADING, RunState.SUCCEEDED, RunState.FAILED, RunState.CANCELLED}
    ),
    RunState.UPLOADING: frozenset({RunState.SUCCEEDED, RunState.FAILED, RunState.CANCELLED}),
}


class RunTransitionError(ValueError):
    """Raised when a requested lifecycle edge is not permitted."""


class RunConflictError(ValueError):
    """Raised when a replay attempts to change an already-sealed run."""


@dataclass(frozen=True)
class RunRecord:
    """Everything required to resume, audit, or prove one execution."""

    run_id: str
    caller_id: str
    idempotency_key: str
    budget: Mapping[str, Any]
    executor: str
    # The worker must be able to resume a run without recovering request-local
    # state.  This deliberately contains a serializable description, never a
    # callable, credential, or open file handle.
    job: Mapping[str, Any] | None = None
    state: RunState = RunState.ACCEPTED
    created_at: datetime | None = None
    updated_at: datetime | None = None
    terminal_reason: str | None = None
    terminal_receipt: Mapping[str, Any] | None = None

    @property
    def is_terminal(self) -> bool:
        return self.state in _TERMINAL_STATES


def new_run_id() -> str:
    """Return an opaque ID which cannot disclose caller or workload details."""
    return secrets.token_urlsafe(24)


def assert_transition(from_state: RunState, to_state: RunState) -> None:
    if to_state not in _TRANSITIONS.get(from_state, frozenset()):
        raise RunTransitionError(f"invalid run transition: {from_state} -> {to_state}")


class Cursor(Protocol):
    def execute(self, query: str, params: tuple[Any, ...] = ()) -> Any: ...
    def fetchone(self) -> Any: ...
    def close(self) -> None: ...


class Connection(Protocol):
    def cursor(self) -> Cursor: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def close(self) -> None: ...


class InMemoryRunRepository:
    """Deterministic test/reference adapter with the same replay semantics."""

    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._records: dict[str, RunRecord] = {}
        self._by_replay_key: dict[tuple[str, str], str] = {}

    def create_or_get(self, record: RunRecord) -> RunRecord:
        key = (record.caller_id, record.idempotency_key)
        existing_id = self._by_replay_key.get(key)
        if existing_id is not None:
            return self._records[existing_id]
        if record.state is not RunState.ACCEPTED:
            raise RunTransitionError("new runs must begin in accepted")
        now = self._clock()
        persisted = replace(
            record, created_at=record.created_at or now, updated_at=record.updated_at or now
        )
        self._records[persisted.run_id] = persisted
        self._by_replay_key[key] = persisted.run_id
        return persisted

    def get(self, run_id: str) -> RunRecord | None:
        return self._records.get(run_id)

    def list_by_states(self, *states: RunState) -> tuple[RunRecord, ...]:
        wanted = frozenset(states)
        return tuple(
            record
            for run_id, record in sorted(self._records.items())
            if record.state in wanted
        )

    def transition(
        self, run_id: str, *, from_state: RunState, to_state: RunState
    ) -> RunRecord | None:
        assert_transition(from_state, to_state)
        record = self._records.get(run_id)
        if record is None or record.state is not from_state:
            return None
        if to_state in _TERMINAL_STATES:
            raise RunTransitionError("terminal transitions must use finalize")
        updated = replace(record, state=to_state, updated_at=self._clock())
        self._records[run_id] = updated
        return updated

    def finalize(
        self,
        run_id: str,
        *,
        from_state: RunState,
        state: RunState,
        reason: str,
        receipt: Mapping[str, Any],
    ) -> RunRecord | None:
        assert_transition(from_state, state)
        if state not in _TERMINAL_STATES:
            raise RunTransitionError("finalize requires a terminal state")
        record = self._records.get(run_id)
        if record is None:
            return None
        if record.is_terminal:
            if (
                record.state is state
                and record.terminal_reason == reason
                and record.terminal_receipt == receipt
            ):
                return record
            raise RunConflictError("terminal receipt already sealed for this run")
        if record.state is not from_state:
            return None
        updated = replace(
            record,
            state=state,
            updated_at=self._clock(),
            terminal_reason=reason,
            terminal_receipt=dict(receipt),
        )
        self._records[run_id] = updated
        return updated

    def cancel(self, run_id: str, *, reason: str, receipt: Mapping[str, Any]) -> RunRecord | None:
        record = self.get(run_id)
        if record is None:
            return None
        if record.is_terminal:
            if (
                record.state is RunState.CANCELLED
                and record.terminal_reason == reason
                and record.terminal_receipt == receipt
            ):
                return record
            raise RunConflictError("terminal receipt already sealed for this run")
        return self.finalize(
            run_id,
            from_state=record.state,
            state=RunState.CANCELLED,
            reason=reason,
            receipt=receipt,
        )


class PostgresRunRepository:
    """Postgres adapter using unique replay keys and guarded lifecycle writes."""

    schema_sql = """
    CREATE TABLE IF NOT EXISTS runs (
        run_id TEXT PRIMARY KEY,
        caller_id TEXT NOT NULL,
        idempotency_key TEXT NOT NULL,
        budget JSONB NOT NULL,
        executor TEXT NOT NULL,
        job JSONB,
        state TEXT NOT NULL CHECK (state IN (
            'accepted', 'queued', 'running', 'uploading', 'succeeded', 'failed', 'cancelled'
        )),
        terminal_reason TEXT,
        terminal_receipt JSONB,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (caller_id, idempotency_key),
        CHECK (
            (state IN ('succeeded', 'failed', 'cancelled')) =
            (terminal_reason IS NOT NULL AND terminal_receipt IS NOT NULL)
        )
    );
    CREATE INDEX IF NOT EXISTS runs_state_idx ON runs (state, created_at);
    ALTER TABLE runs ADD COLUMN IF NOT EXISTS job JSONB;
    """

    def __init__(self, connection_factory: Callable[[], Connection]) -> None:
        self._connection_factory = connection_factory

    def initialize(self) -> None:
        self._write(self.schema_sql, ())

    def create_or_get(self, record: RunRecord) -> RunRecord:
        if record.state is not RunState.ACCEPTED:
            raise RunTransitionError("new runs must begin in accepted")
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """INSERT INTO runs (
                       run_id, caller_id, idempotency_key, budget, executor, job, state
                   )
                   VALUES (%s, %s, %s, %s::jsonb, %s, %s::jsonb, %s)
                   ON CONFLICT (caller_id, idempotency_key) DO NOTHING
                   RETURNING run_id, caller_id, idempotency_key, budget, executor, state,
                             created_at, updated_at, terminal_reason, terminal_receipt, job""",
                (
                    record.run_id,
                    record.caller_id,
                    record.idempotency_key,
                    json.dumps(dict(record.budget)),
                    record.executor,
                    json.dumps(dict(record.job)) if record.job is not None else None,
                    record.state.value,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                cursor.execute(
                    self._select_by_replay_sql, (record.caller_id, record.idempotency_key)
                )
                row = cursor.fetchone()
            connection.commit()
            return self._record_from_row(row)
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    _select_fields = (
        "run_id, caller_id, idempotency_key, budget, executor, state, created_at, updated_at, "
        "terminal_reason, terminal_receipt, job"
    )
    _select_by_replay_sql = (
        f"SELECT {_select_fields} FROM runs WHERE caller_id = %s AND idempotency_key = %s"
    )

    def get(self, run_id: str) -> RunRecord | None:
        row = self._read(f"SELECT {self._select_fields} FROM runs WHERE run_id = %s", (run_id,))
        return self._record_from_row(row) if row is not None else None

    def list_by_states(self, *states: RunState) -> tuple[RunRecord, ...]:
        if not states:
            return ()
        placeholders = ", ".join(["%s"] * len(states))
        rows = self._read_all(
            f"SELECT {self._select_fields} FROM runs WHERE state IN ({placeholders}) "
            "ORDER BY run_id",
            tuple(state.value for state in states),
        )
        return tuple(self._record_from_row(row) for row in rows)

    def transition(
        self, run_id: str, *, from_state: RunState, to_state: RunState
    ) -> RunRecord | None:
        assert_transition(from_state, to_state)
        if to_state in _TERMINAL_STATES:
            raise RunTransitionError("terminal transitions must use finalize")
        row = self._write(
            f"""UPDATE runs SET state = %s, updated_at = NOW()
                WHERE run_id = %s AND state = %s
                RETURNING {self._select_fields}""",
            (to_state.value, run_id, from_state.value),
            fetch_one=True,
        )
        return self._record_from_row(row) if row is not None else None

    def finalize(
        self,
        run_id: str,
        *,
        from_state: RunState,
        state: RunState,
        reason: str,
        receipt: Mapping[str, Any],
    ) -> RunRecord | None:
        assert_transition(from_state, state)
        if state not in _TERMINAL_STATES:
            raise RunTransitionError("finalize requires a terminal state")
        row = self._write(
            f"""UPDATE runs SET state = %s,
                               terminal_reason = %s,
                               terminal_receipt = %s::jsonb,
                               updated_at = NOW()
                WHERE run_id = %s AND state = %s
                RETURNING {self._select_fields}""",
            (state.value, reason, json.dumps(dict(receipt)), run_id, from_state.value),
            fetch_one=True,
        )
        if row is not None:
            return self._record_from_row(row)
        existing = self.get(run_id)
        if existing is not None and existing.is_terminal:
            if (
                existing.state is state
                and existing.terminal_reason == reason
                and existing.terminal_receipt == receipt
            ):
                return existing
            raise RunConflictError("terminal receipt already sealed for this run")
        return None

    def cancel(self, run_id: str, *, reason: str, receipt: Mapping[str, Any]) -> RunRecord | None:
        existing = self.get(run_id)
        if existing is None:
            return None
        if existing.is_terminal:
            if (
                existing.state is RunState.CANCELLED
                and existing.terminal_reason == reason
                and existing.terminal_receipt == receipt
            ):
                return existing
            raise RunConflictError("terminal receipt already sealed for this run")
        return self.finalize(
            run_id,
            from_state=existing.state,
            state=RunState.CANCELLED,
            reason=reason,
            receipt=receipt,
        )

    def _read(self, query: str, params: tuple[Any, ...]) -> Any:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(query, params)
            return cursor.fetchone()
        finally:
            cursor.close()
            connection.close()

    def _read_all(self, query: str, params: tuple[Any, ...]) -> tuple[Any, ...]:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(query, params)
            return tuple(cursor.fetchall())
        finally:
            cursor.close()
            connection.close()

    def _write(self, query: str, params: tuple[Any, ...], *, fetch_one: bool = False) -> Any:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(query, params)
            row = cursor.fetchone() if fetch_one else None
            connection.commit()
            return row
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def _record_from_row(row: tuple[Any, ...]) -> RunRecord:
        budget, receipt, job = row[3], row[9], row[10]
        if isinstance(budget, str):
            budget = json.loads(budget)
        if isinstance(receipt, str):
            receipt = json.loads(receipt)
        if isinstance(job, str):
            job = json.loads(job)
        return RunRecord(
            run_id=row[0],
            caller_id=row[1],
            idempotency_key=row[2],
            budget=budget,
            executor=row[4],
            job=job,
            state=RunState(row[5]),
            created_at=row[6],
            updated_at=row[7],
            terminal_reason=row[8],
            terminal_receipt=receipt,
        )
