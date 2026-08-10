"""Durable lifecycle records for asynchronous Star executions."""

from .diagnostics import CleanupLag, OperatorRunHealth, build_operator_health
from .domain import (
    InMemoryRunRepository,
    PostgresRunRepository,
    RunConflictError,
    RunRecord,
    RunState,
    RunTransitionError,
    new_run_id,
)
from .queue import (
    FailureDisposition,
    InMemoryQueueBackend,
    ManagedRunWorker,
    QueueLease,
    QueueStats,
    RedisQueueBackend,
)
from .reconcile import AuditEvent, InMemoryAuditLog, RunReconciler
from .submission import ManagedRunSubmission
from .worker import (
    JobHandlerRegistry,
    RunWorkerRuntime,
    UnknownJobError,
    WorkerConfigurationError,
    WorkerSettings,
    build_runtime,
)

__all__ = [
    "AuditEvent",
    "CleanupLag",
    "FailureDisposition",
    "InMemoryAuditLog",
    "InMemoryQueueBackend",
    "InMemoryRunRepository",
    "JobHandlerRegistry",
    "ManagedRunSubmission",
    "ManagedRunWorker",
    "OperatorRunHealth",
    "PostgresRunRepository",
    "QueueLease",
    "QueueStats",
    "RedisQueueBackend",
    "RunConflictError",
    "RunRecord",
    "RunReconciler",
    "RunState",
    "RunTransitionError",
    "RunWorkerRuntime",
    "UnknownJobError",
    "WorkerConfigurationError",
    "WorkerSettings",
    "build_operator_health",
    "build_runtime",
    "new_run_id",
]
