"""Durable lifecycle records for asynchronous Star executions."""

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
    RedisQueueBackend,
)
from .worker import (
    JobHandlerRegistry,
    RunWorkerRuntime,
    UnknownJobError,
    WorkerConfigurationError,
    WorkerSettings,
    build_runtime,
)

__all__ = [
    "FailureDisposition",
    "InMemoryQueueBackend",
    "InMemoryRunRepository",
    "JobHandlerRegistry",
    "ManagedRunWorker",
    "PostgresRunRepository",
    "QueueLease",
    "RedisQueueBackend",
    "RunConflictError",
    "RunRecord",
    "RunState",
    "RunTransitionError",
    "RunWorkerRuntime",
    "UnknownJobError",
    "WorkerConfigurationError",
    "WorkerSettings",
    "build_runtime",
    "new_run_id",
]
