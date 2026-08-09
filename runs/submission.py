"""Control-plane admission for serializable managed CPU jobs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .domain import RunRecord, new_run_id
from .queue import ManagedRunWorker


class ManagedRunSubmission:
    """Persist before enqueueing; request handlers never run CPU workloads."""

    def __init__(self, worker: ManagedRunWorker) -> None:
        self._worker = worker

    def submit(
        self, *, caller_id: str, idempotency_key: str, kind: str, input: Mapping[str, Any]
    ) -> RunRecord:
        if kind not in {"html-to-pdf", "csv-report", "image-transform"}:
            raise ValueError("unsupported managed workload")
        record = self._worker.runs.create_or_get(
            RunRecord(
                new_run_id(),
                caller_id,
                idempotency_key,
                budget={"executor": "managed-cpu-worker"},
                executor="managed-cpu-worker",
                job={"kind": kind, "input": dict(input)},
            )
        )
        self._worker.enqueue(record.run_id)
        return self._worker.runs.get(record.run_id) or record
