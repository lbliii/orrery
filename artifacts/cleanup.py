"""Bounded physical-retention reaper for expired durable artifacts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from .domain import ArtifactRecord
from .storage import ArtifactStorage


class ExpiryRepository(Protocol):
    def claim_expired(
        self, *, now: datetime, batch_size: int, retry_before: datetime
    ) -> list[ArtifactRecord]: ...

    def mark_deleted(self, artifact_id: str) -> bool: ...


@dataclass(frozen=True)
class CleanupResult:
    claimed: int = 0
    deleted: int = 0
    failed: int = 0


class ArtifactCleanupService:
    """Deletes only durably claimed expired objects and leaves failures retryable."""

    def __init__(
        self,
        repository: ExpiryRepository,
        storage: ArtifactStorage,
        *,
        clock: Callable[[], datetime] | None = None,
        retry_after: timedelta = timedelta(minutes=5),
    ) -> None:
        if retry_after <= timedelta(0):
            raise ValueError("retry_after must be positive")
        self._repository, self._storage = repository, storage
        self._clock, self._retry_after = clock or (lambda: datetime.now(UTC)), retry_after

    def cleanup_once(self, *, batch_size: int = 100) -> CleanupResult:
        now = self._clock()
        claimed = self._repository.claim_expired(
            now=now, batch_size=batch_size, retry_before=now - self._retry_after
        )
        deleted = failed = 0
        for artifact in claimed:
            try:
                self._storage.delete(key=artifact.storage_key)
                if self._repository.mark_deleted(artifact.artifact_id):
                    deleted += 1
            except Exception:
                failed += 1
        return CleanupResult(claimed=len(claimed), deleted=deleted, failed=failed)
