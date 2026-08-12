"""Namespace metadata for private Skill DNS zones."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

DEFAULT_RETENTION_DAYS = 90


@dataclass(frozen=True, slots=True)
class Namespace:
    """One provisioned tenant namespace (path / name-prefix tenancy)."""

    id: str
    created_at: datetime
    retention_days: int = DEFAULT_RETENTION_DAYS

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "retention_days": self.retention_days,
        }
