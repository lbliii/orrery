"""Operator diagnostics summary for #158 — no bytes or credentials."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from runs import (
    CleanupLag,
    InMemoryAuditLog,
    InMemoryQueueBackend,
    build_operator_health,
)
from runs.reconcile import AuditEvent


def test_operator_health_exposes_queue_and_audit_counters_only() -> None:
    clock = datetime(2026, 8, 10, 15, 0, tzinfo=UTC)
    queue = InMemoryQueueBackend(clock=lambda: clock)
    queue.enqueue("a")
    queue.enqueue("b")
    queue.claim("w1", lease_for=timedelta(seconds=30), max_attempts=3)
    audit = InMemoryAuditLog()
    audit.append(
        AuditEvent(
            kind="lease_loss",
            run_id="a",
            reason="lease_lost",
            evidence={"worker_id": "w1"},
            at=clock,
        )
    )
    health = build_operator_health(
        queue=queue,
        audit=audit,
        cleanup=CleanupLag(claimed=2, deleted=1, failed=0, last_batch_at="2026-08-10T15:00:00Z"),
        artifact_bytes_total=4096,
    )
    payload = health.as_dict()
    assert payload["role"] == "managed-worker"
    assert payload["queue"]["ready_depth"] >= 1
    assert payload["queue"]["leased_depth"] == 1
    assert payload["audits"]["lease_loss"] == 1
    assert payload["cleanup"]["deleted"] == 1
    assert payload["artifact_bytes_total"] == 4096
    assert "token" not in str(payload["recent"])
    assert "credential" not in str(payload).lower()
