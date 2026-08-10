"""Bounded operator diagnostics for managed runs (#158).

Summaries expose counters and ages only — never artifact bodies, credentials,
lease tokens beyond presence, or caller payloads.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from .queue import QueueStats
from .reconcile import AuditLog


@dataclass(frozen=True)
class CleanupLag:
    claimed: int = 0
    deleted: int = 0
    failed: int = 0
    last_batch_at: str | None = None


@dataclass(frozen=True)
class OperatorRunHealth:
    """Compact operator view — safe to expose on the private worker probe."""

    status: str
    role: str
    queue: Mapping[str, Any]
    audits: Mapping[str, int]
    cleanup: Mapping[str, Any]
    artifact_bytes_total: int | None
    recent: tuple[Mapping[str, Any], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "role": self.role,
            "queue": dict(self.queue),
            "audits": dict(self.audits),
            "cleanup": dict(self.cleanup),
            "artifact_bytes_total": self.artifact_bytes_total,
            "recent": [dict(item) for item in self.recent],
        }


class QueueDiagnostics(Protocol):
    def stats(self) -> QueueStats: ...


def build_operator_health(
    *,
    queue: QueueDiagnostics,
    audit: AuditLog,
    cleanup: CleanupLag | None = None,
    artifact_bytes_total: int | None = None,
    recent_limit: int = 10,
) -> OperatorRunHealth:
    stats = queue.stats()
    lag = cleanup or CleanupLag()
    return OperatorRunHealth(
        status="ok",
        role="managed-worker",
        queue={
            "ready_depth": stats.ready_depth,
            "leased_depth": stats.leased_depth,
            "dead_letter_depth": stats.dead_letter_depth,
            "oldest_ready_age_seconds": stats.oldest_ready_age_seconds,
            "oldest_lease_age_seconds": stats.oldest_lease_age_seconds,
        },
        audits=dict(audit.counts_by_kind()),
        cleanup={
            "claimed": lag.claimed,
            "deleted": lag.deleted,
            "failed": lag.failed,
            "last_batch_at": lag.last_batch_at,
        },
        artifact_bytes_total=artifact_bytes_total,
        recent=tuple(event.as_dict() for event in audit.list(limit=recent_limit)),
    )
