"""Ephemeral artifact storage for rendered PDF outputs.

The first real renderer intentionally keeps artifacts in-process.  The store
gives callers a short-lived URL now while leaving durable object storage as an
explicit future replacement rather than a hidden dependency.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass

ARTIFACT_TTL_SECONDS = 15 * 60


@dataclass(frozen=True)
class PdfArtifact:
    """A rendered PDF and the metadata needed to retrieve and verify it."""

    artifact_id: str
    data: bytes
    sha256: str
    expires_at: float


class PdfArtifactStore:
    """Small process-local store with bounded-lifetime PDF artifacts."""

    def __init__(self, *, ttl_seconds: int = ARTIFACT_TTL_SECONDS) -> None:
        self._ttl_seconds = ttl_seconds
        self._artifacts: dict[str, PdfArtifact] = {}

    def put(self, data: bytes) -> PdfArtifact:
        """Store PDF bytes and return their retrieval metadata."""
        self._purge_expired()
        artifact_id = secrets.token_urlsafe(18)
        artifact = PdfArtifact(
            artifact_id=artifact_id,
            data=data,
            sha256=f"sha256:{hashlib.sha256(data).hexdigest()}",
            expires_at=time.time() + self._ttl_seconds,
        )
        self._artifacts[artifact_id] = artifact
        return artifact

    def get(self, artifact_id: str) -> PdfArtifact | None:
        """Return a live artifact, removing it if it has expired."""
        artifact = self._artifacts.get(artifact_id)
        if artifact is None:
            return None
        if artifact.expires_at <= time.time():
            self._artifacts.pop(artifact_id, None)
            return None
        return artifact

    def _purge_expired(self) -> None:
        now = time.time()
        for artifact_id, artifact in tuple(self._artifacts.items()):
            if artifact.expires_at <= now:
                self._artifacts.pop(artifact_id, None)


artifact_store = PdfArtifactStore()
