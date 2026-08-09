"""Authorization, safe headers, and audit seam for artifact delivery."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

from .domain import ArtifactRecord

_LOG = logging.getLogger("orrery.artifacts")
_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class DownloadAuditEvent:
    artifact_id: str
    outcome: str
    content_type: str | None = None


class DownloadAuditSink(Protocol):
    def record(self, event: DownloadAuditEvent) -> None: ...


class LoggingDownloadAudit:
    """Default audit sink intentionally excludes object/capability URLs."""

    def record(self, event: DownloadAuditEvent) -> None:
        _LOG.info(
            "artifact_download",
            extra={
                "artifact_ref": event.artifact_id,
                "outcome": event.outcome,
                "content_type": event.content_type,
            },
        )


def audit_artifact_ref(value: str) -> str:
    """Return a non-reversible audit reference; never log caller-supplied IDs."""
    return f"sha256:{sha256(value.encode('utf-8', 'surrogatepass')).hexdigest()[:16]}"


def policy_allows(record: ArtifactRecord, *, receipt_holder: bool, owner_id: str | None) -> bool:
    if record.policy.access == "public":
        return True
    if record.policy.access == "receipt-holder":
        return receipt_holder
    return (
        record.policy.access == "private" and bool(owner_id) and owner_id == record.policy.owner_id
    )


def safe_attachment_filename(filename: str, *, fallback: str = "artifact.bin") -> str:
    """Return an ASCII attachment filename without header/path injection."""
    candidate = _SAFE_FILENAME.sub("_", filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1])
    candidate = candidate.strip("._")[:180]
    return candidate or fallback
