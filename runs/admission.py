"""Pre-persist admission gates for managed CPU runs."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any, Protocol

from stars._core.execution import MAX_INPUT_BYTES

# Closed workload allowlist; mirrors stars/cpu_workloads.py worker policy pins.
_KIND_POLICIES: dict[str, dict[str, int]] = {
    "html-to-pdf": {
        "cpu_millicores": 250,
        "wall_time_seconds": 30,
        "max_output_bytes": 1_048_576,
        "max_input_bytes": MAX_INPUT_BYTES,
    },
    "csv-report": {
        "cpu_millicores": 250,
        "wall_time_seconds": 30,
        "max_output_bytes": 1_048_576,
        "max_input_bytes": 1_048_576,
    },
    "image-transform": {
        "cpu_millicores": 250,
        "wall_time_seconds": 30,
        "max_output_bytes": 1_048_576,
        "max_input_bytes": 1_048_576,
    },
}

_SUPPORTED_KINDS = frozenset(_KIND_POLICIES)


class RunAdmissionError(ValueError):
    """Raised before a run record is created or enqueued."""

    def __init__(self, *, code: str, policy: Mapping[str, Any]) -> None:
        self.code = code
        self.policy = dict(policy)
        super().__init__(code)


class ActiveRunCounter(Protocol):
    def count_active_by_caller(self, caller_id: str) -> int: ...


def max_active_per_caller() -> int:
    raw = os.environ.get("ORRERY_RUN_MAX_ACTIVE_PER_CALLER", "3")
    try:
        limit = int(raw)
    except ValueError as error:
        raise ValueError("ORRERY_RUN_MAX_ACTIVE_PER_CALLER must be an integer") from error
    if limit < 1:
        raise ValueError("ORRERY_RUN_MAX_ACTIVE_PER_CALLER must be positive")
    return limit


def policy_for_kind(kind: str) -> dict[str, int]:
    policy = _KIND_POLICIES.get(kind)
    if policy is None:
        raise RunAdmissionError(code="unsupported_kind", policy={"kind": kind})
    return dict(policy)


def budget_snapshot(kind: str) -> dict[str, object]:
    policy = policy_for_kind(kind)
    return {"executor": "managed-cpu-worker", "policy": policy}


def serialized_input_bytes(input: Mapping[str, Any]) -> int:
    return len(json.dumps(dict(input), separators=(",", ":"), sort_keys=True).encode("utf-8"))


def check_admission(
    *,
    runs: ActiveRunCounter,
    caller_id: str,
    kind: str,
    input: Mapping[str, Any],
    max_active: int | None = None,
) -> dict[str, int]:
    """Validate kind, input size, and caller concurrency before persist/enqueue."""
    if kind not in _SUPPORTED_KINDS:
        raise RunAdmissionError(code="unsupported_kind", policy={"kind": kind})
    policy = dict(_KIND_POLICIES[kind])
    input_bytes = serialized_input_bytes(input)
    if input_bytes > policy["max_input_bytes"]:
        raise RunAdmissionError(
            code="input_too_large",
            policy={
                "kind": kind,
                "max_input_bytes": policy["max_input_bytes"],
                "input_bytes": input_bytes,
            },
        )
    limit = max_active if max_active is not None else max_active_per_caller()
    active = runs.count_active_by_caller(caller_id)
    if active >= limit:
        raise RunAdmissionError(
            code="concurrency_exhausted",
            policy={"max_active_per_caller": limit, "active": active},
        )
    return policy
