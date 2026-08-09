"""Managed CPU policy stays serializable and worker-only (#135)."""

from __future__ import annotations

import pytest

from stars._core import (
    ManagedCPUExecutionPolicy,
    ManagedCPUExecutionPolicyError,
    ManagedCPUWorkload,
)


def _policy(**changes: object) -> ManagedCPUExecutionPolicy:
    values: dict[str, object] = {
        "cpu_millicores": 500,
        "memory_bytes": 512 * 1024 * 1024,
        "wall_time_seconds": 60,
        "max_input_bytes": 1024 * 1024,
        "max_output_bytes": 4 * 1024 * 1024,
        "allowed_egress": (),
    }
    values.update(changes)
    return ManagedCPUExecutionPolicy(**values)  # type: ignore[arg-type]


def test_default_deny_policy_is_sealed_into_receipt_provenance() -> None:
    workload = ManagedCPUWorkload(
        image_digest="sha256:" + "a" * 64,
        command=("/app/run", "--json"),
        policy=_policy(),
    )

    assert workload.receipt_fields() == {
        "execution_mode": "managed-cpu",
        "image_digest": "sha256:" + "a" * 64,
        "limits": {
            "cpu_millicores": 500,
            "memory_bytes": 512 * 1024 * 1024,
            "wall_time_seconds": 60,
            "max_input_bytes": 1024 * 1024,
            "max_output_bytes": 4 * 1024 * 1024,
        },
        "allowed_egress": [],
    }


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"cpu_millicores": 4_001}, "cpu_millicores"),
        ({"memory_bytes": 0}, "memory_bytes"),
        ({"allowed_egress": ("http://example.com",)}, "HTTPS origins"),
        ({"allowed_egress": ("https://example.com/path",)}, "HTTPS origins"),
    ],
)
def test_policy_rejects_unenforceable_limits_or_egress(
    changes: dict[str, object], message: str
) -> None:
    with pytest.raises(ManagedCPUExecutionPolicyError, match=message):
        _policy(**changes)


def test_workload_rejects_unpinned_image_and_shell_command() -> None:
    with pytest.raises(ManagedCPUExecutionPolicyError, match="image_digest"):
        ManagedCPUWorkload("latest", ("/app/run",), _policy())
    with pytest.raises(ManagedCPUExecutionPolicyError, match="must not invoke a shell"):
        ManagedCPUWorkload("sha256:" + "a" * 64, ("/bin/sh", "-c", "run"), _policy())
