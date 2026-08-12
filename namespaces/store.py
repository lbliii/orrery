"""In-process namespace registry (MVP durability bar)."""

from __future__ import annotations

import threading
from datetime import UTC, datetime

from .models import DEFAULT_RETENTION_DAYS, Namespace

_store: dict[str, Namespace] = {}
_lock = threading.Lock()


def get_namespace(namespace_id: str) -> Namespace | None:
    key = namespace_id.strip().lower()
    with _lock:
        return _store.get(key)


def list_namespaces() -> tuple[Namespace, ...]:
    with _lock:
        return tuple(sorted(_store.values(), key=lambda ns: ns.id))


def register_namespace(
    namespace_id: str,
    *,
    retention_days: int = DEFAULT_RETENTION_DAYS,
    created_at: datetime | None = None,
) -> Namespace:
    """Insert a namespace record; caller must validate slug and uniqueness."""
    key = namespace_id.strip().lower()
    record = Namespace(
        id=key,
        created_at=created_at or datetime.now(tz=UTC),
        retention_days=retention_days,
    )
    with _lock:
        _store[key] = record
    return record


def reset_namespace_store() -> None:
    """Clear the process-wide registry (tests)."""
    with _lock:
        _store.clear()
