"""Acceptance coverage for #134 run persistence and replay semantics."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from runs import (
    InMemoryRunRepository,
    PostgresRunRepository,
    RunConflictError,
    RunRecord,
    RunState,
    RunTransitionError,
)


def _run(*, run_id: str = "run-a", key: str = "request-a") -> RunRecord:
    return RunRecord(
        run_id=run_id,
        caller_id="agent:alice",
        idempotency_key=key,
        budget={"max_cents": 25},
        executor="managed-cpu",
    )


def test_api_facing_repository_replays_by_caller_and_idempotency_key() -> None:
    repository = InMemoryRunRepository(clock=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    first = repository.create_or_get(_run())
    replay = repository.create_or_get(_run(run_id="ignored-on-replay"))

    assert replay == first
    assert first.state is RunState.ACCEPTED
    assert first.created_at is not None


def test_run_state_machine_rejects_skips_and_cancellation_is_terminal() -> None:
    repository = InMemoryRunRepository()
    repository.create_or_get(_run())

    with pytest.raises(RunTransitionError, match="accepted -> running"):
        repository.transition("run-a", from_state=RunState.ACCEPTED, to_state=RunState.RUNNING)

    cancelled = repository.cancel("run-a", reason="caller_cancelled", receipt={"kind": "cancel"})
    assert cancelled is not None and cancelled.state is RunState.CANCELLED
    with pytest.raises(RunConflictError, match="sealed"):
        repository.cancel("run-a", reason="different", receipt={"kind": "cancel"})


def test_terminal_receipt_is_idempotent_by_run_id() -> None:
    repository = InMemoryRunRepository()
    repository.create_or_get(_run())
    queued = repository.transition("run-a", from_state=RunState.ACCEPTED, to_state=RunState.QUEUED)
    assert queued is not None
    running = repository.transition("run-a", from_state=RunState.QUEUED, to_state=RunState.RUNNING)
    assert running is not None
    receipt = {"artifact_id": "opaque", "sha256": "sha256:abc"}
    first = repository.finalize(
        "run-a",
        from_state=RunState.RUNNING,
        state=RunState.SUCCEEDED,
        reason="complete",
        receipt=receipt,
    )
    replay = repository.finalize(
        "run-a",
        from_state=RunState.RUNNING,
        state=RunState.SUCCEEDED,
        reason="complete",
        receipt=receipt,
    )

    assert replay == first
    assert first is not None and first.terminal_receipt == receipt


def test_postgres_repository_uses_unique_replay_key_and_guarded_transition() -> None:
    connection = _FakeConnection(
        return_rows=[
            (
                "run-a",
                "agent:alice",
                "request-a",
                {"max_cents": 25},
                "managed-cpu",
                "accepted",
                None,
                None,
                None,
                None,
                None,
            ),
            (
                "run-a",
                "agent:alice",
                "request-a",
                {"max_cents": 25},
                "managed-cpu",
                "queued",
                None,
                None,
                None,
                None,
                None,
            ),
        ]
    )
    repository = PostgresRunRepository(lambda: connection)

    created = repository.create_or_get(_run())
    transitioned = repository.transition(
        "run-a", from_state=RunState.ACCEPTED, to_state=RunState.QUEUED
    )

    assert created.run_id == "run-a"
    assert transitioned is not None and transitioned.state is RunState.QUEUED
    insert_query, _ = connection.cursor_instance.calls[0]
    transition_query, transition_params = connection.cursor_instance.calls[1]
    assert "ON CONFLICT (caller_id, idempotency_key) DO NOTHING" in insert_query
    assert "WHERE run_id = %s AND state = %s" in transition_query
    assert transition_params == ("queued", "run-a", "accepted")


class _FakeCursor:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.rows = rows

    def execute(self, query: str, params: tuple[object, ...] = ()) -> None:
        self.calls.append((query, params))

    def fetchone(self) -> tuple[object, ...] | None:
        return self.rows.pop(0) if self.rows else None

    def close(self) -> None:
        pass


class _FakeConnection:
    def __init__(self, *, return_rows: list[tuple[object, ...]]) -> None:
        self.cursor_instance = _FakeCursor(return_rows)

    def cursor(self) -> _FakeCursor:
        return self.cursor_instance

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        pass
