"""Safe, serializable execution specifications for managed CPU Stars.

The API accepts an image digest and resource policy, never source code or a
callable. A worker is responsible for starting that image in its own isolated
runtime; this module intentionally does not provide an in-process runner.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit


class ManagedCPUExecutionPolicyError(ValueError):
    """A managed CPU policy is unsafe or cannot be enforced by a worker."""


_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_SHELLS = frozenset({"sh", "bash", "zsh", "fish", "dash", "/bin/sh", "/bin/bash"})

# Platform ceilings keep a publisher manifest from reserving an unbounded
# Railway worker. Individual Stars choose lower values in their own policy.
MAX_CPU_MILLICORES = 4_000
MAX_MEMORY_BYTES = 8 * 1024 * 1024 * 1024
MAX_WALL_TIME_SECONDS = 15 * 60
MAX_INPUT_BYTES = 16 * 1024 * 1024
MAX_OUTPUT_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ManagedCPUExecutionPolicy:
    """Hard limits passed unchanged to the isolated worker runtime."""

    cpu_millicores: int
    memory_bytes: int
    wall_time_seconds: int
    max_input_bytes: int
    max_output_bytes: int
    allowed_egress: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _positive_with_ceiling("cpu_millicores", self.cpu_millicores, MAX_CPU_MILLICORES)
        _positive_with_ceiling("memory_bytes", self.memory_bytes, MAX_MEMORY_BYTES)
        _positive_with_ceiling("wall_time_seconds", self.wall_time_seconds, MAX_WALL_TIME_SECONDS)
        _positive_with_ceiling("max_input_bytes", self.max_input_bytes, MAX_INPUT_BYTES)
        _positive_with_ceiling("max_output_bytes", self.max_output_bytes, MAX_OUTPUT_BYTES)
        if len(set(self.allowed_egress)) != len(self.allowed_egress):
            raise ManagedCPUExecutionPolicyError("allowed_egress must not contain duplicates")
        for origin in self.allowed_egress:
            _validate_https_origin(origin)

    def receipt_fields(self, *, image_digest: str) -> dict[str, object]:
        """Return immutable execution provenance to seal in a final receipt."""
        _validate_image_digest(image_digest)
        return {
            "execution_mode": "managed-cpu",
            "image_digest": image_digest,
            "limits": {
                "cpu_millicores": self.cpu_millicores,
                "memory_bytes": self.memory_bytes,
                "wall_time_seconds": self.wall_time_seconds,
                "max_input_bytes": self.max_input_bytes,
                "max_output_bytes": self.max_output_bytes,
            },
            # An empty list explicitly means default-deny network.
            "allowed_egress": list(self.allowed_egress),
        }


@dataclass(frozen=True, slots=True)
class ManagedCPUWorkload:
    """A worker-only workload reference; executable code is never accepted."""

    image_digest: str
    command: tuple[str, ...]
    policy: ManagedCPUExecutionPolicy

    def __post_init__(self) -> None:
        _validate_image_digest(self.image_digest)
        if not self.command or any(not isinstance(part, str) or not part for part in self.command):
            raise ManagedCPUExecutionPolicyError("command must be a non-empty argv")
        if self.command[0] in _SHELLS:
            raise ManagedCPUExecutionPolicyError("command must not invoke a shell")

    def receipt_fields(self) -> dict[str, object]:
        return self.policy.receipt_fields(image_digest=self.image_digest)


def _positive_with_ceiling(name: str, value: int, ceiling: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 < value <= ceiling:
        raise ManagedCPUExecutionPolicyError(f"{name} must be a positive integer at most {ceiling}")


def _validate_image_digest(value: str) -> None:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise ManagedCPUExecutionPolicyError("image_digest must be a sha256 digest")


def _validate_https_origin(value: str) -> None:
    if not isinstance(value, str) or not value:
        raise ManagedCPUExecutionPolicyError("allowed_egress entries must be HTTPS origins")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise ManagedCPUExecutionPolicyError("allowed_egress entries must be HTTPS origins")
