"""Caller allowlist enforcement for private namespace paths (#30)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .models import DEFAULT_RETENTION_DAYS
from .store import get_namespace

if TYPE_CHECKING:
    from catalog.models import ResolveRecord

CALLER_HEADER = "X-Orrery-Caller"

#: Nodes that scope the public sky — no caller gate.
_PUBLIC_NODES = frozenset({"", "public", "docs"})


def caller_from_header(value: str | None) -> str | None:
    """Normalize a caller id from the machine header."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def is_private_namespace_node(node: str | None) -> bool:
    """True when gaze/resolve scopes to a tenant namespace."""
    normalized = (node or "public").strip().lower()
    return normalized not in _PUBLIC_NODES


def retention_days_for(namespace_id: str) -> int:
    """Envelope retention hook — local store lookup (audit export stub)."""
    record = get_namespace(namespace_id.strip().lower())
    if record is None:
        return DEFAULT_RETENTION_DAYS
    return record.retention_days


def authorize_private_namespace(
    namespace_id: str,
    caller_id: str | None,
) -> dict[str, object] | None:
    """Return a forbidden payload when caller is not on the namespace allowlist.

    Deny-by-default only when ``caller_allowlist`` is non-empty; empty allowlist
    keeps backward-compatible open access for provisioned namespaces.
    """
    key = namespace_id.strip().lower()
    record = get_namespace(key)
    if record is None or not record.caller_allowlist:
        return None
    if caller_id is not None and caller_id in record.caller_allowlist:
        return None
    return {
        "error": "caller_not_allowed",
        "namespace": key,
        "status": "forbidden",
    }


def authorize_private_record(
    record: ResolveRecord,
    caller_id: str | None,
) -> dict[str, object] | None:
    """Gate resolve on private catalog rows when a namespace allowlist is set."""
    if record.visibility != "private":
        return None
    namespace_id = record.namespace
    if namespace_id is None:
        return None
    return authorize_private_namespace(namespace_id, caller_id)
