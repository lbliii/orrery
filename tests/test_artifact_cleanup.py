"""Acceptance coverage for #131 bounded physical artifact retention."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from artifacts.cleanup import ArtifactCleanupService
from artifacts.domain import ArtifactPolicy, ArtifactRecord, ArtifactState


def _record(artifact_id: str, state: ArtifactState = ArtifactState.AVAILABLE) -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id,
        f"artifacts/{artifact_id}",
        "a" * 64,
        1,
        "text/plain",
        "x.txt",
        datetime(2026, 8, 9, tzinfo=UTC) - timedelta(seconds=1),
        ArtifactPolicy(),
        state,
    )


def test_cleanup_deletes_claimed_expired_artifacts() -> None:
    repository, storage = _Repository([_record("expired")]), _Storage()
    result = ArtifactCleanupService(
        repository, storage, clock=lambda: datetime(2026, 8, 9, tzinfo=UTC)
    ).cleanup_once(batch_size=10)

    assert result.claimed == result.deleted == 1
    assert storage.deleted == ["artifacts/expired"]
    assert repository.deleted == ["expired"]
    assert repository.calls[0]["batch_size"] == 10


def test_storage_failure_leaves_deleting_claim_for_safe_later_retry() -> None:
    repository, storage = (
        _Repository([_record("retry", ArtifactState.DELETING)]),
        _Storage(fail=True),
    )
    now = datetime(2026, 8, 9, tzinfo=UTC)
    result = ArtifactCleanupService(repository, storage, clock=lambda: now).cleanup_once()

    assert (result.claimed, result.deleted, result.failed) == (1, 0, 1)
    assert repository.deleted == []
    assert repository.calls[0]["retry_before"] == now - timedelta(minutes=5)


class _Repository:
    def __init__(self, claimed: list[ArtifactRecord]) -> None:
        self.claimed, self.deleted, self.calls = claimed, [], []

    def claim_expired(self, **kwargs: object) -> list[ArtifactRecord]:
        self.calls.append(kwargs)
        return self.claimed

    def mark_deleted(self, artifact_id: str) -> bool:
        self.deleted.append(artifact_id)
        return True


class _Storage:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail, self.deleted = fail, []

    def delete(self, *, key: str) -> None:
        if self.fail:
            raise OSError("object store unavailable")
        self.deleted.append(key)
