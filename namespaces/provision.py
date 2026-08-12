"""Namespace provisioning — store + catalog side effects."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from catalog.dns import mcp_url
from catalog.models import ResolveRecord

from .store import get_namespace, register_namespace
from .validation import is_reserved_slug, is_valid_slug, normalize_slug

if TYPE_CHECKING:
    from catalog.store import Catalog


class ProvisionError(Exception):
    """Structured provisioning failure (maps to HTTP 400)."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _demo_record(namespace_id: str) -> ResolveRecord:
    """One private fixture star so gaze/resolve pills appear for new tenants."""
    return ResolveRecord(
        name=f"{namespace_id}/demo",
        kind="star",
        visibility="private",
        description=f"Demo private star for the {namespace_id} namespace",
        endpoint=mcp_url("/s/demo", namespace=namespace_id),
        key_id=f"{namespace_id}-demo-1",
        content_digest="sha256:demo000…",
        tools=("ping",),
    )


def _catalog_has_namespace(catalog: Catalog, namespace_id: str) -> bool:
    return any((record.namespace or "").lower() == namespace_id for record in catalog.all())


def _normalize_caller_allowlist(raw: object) -> tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ProvisionError("invalid_caller_allowlist")
    entries: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise ProvisionError("invalid_caller_allowlist")
        entries.append(item.strip())
    return tuple(entries)


def _normalize_retention_days(raw: object) -> int:
    from .models import DEFAULT_RETENTION_DAYS

    if raw is None:
        return DEFAULT_RETENTION_DAYS
    if not isinstance(raw, int) or isinstance(raw, bool):
        raise ProvisionError("invalid_retention_days")
    if raw < 1 or raw > 3650:
        raise ProvisionError("invalid_retention_days")
    return raw


def provision_namespace(
    raw_id: str,
    *,
    catalog: Catalog,
    retention_days: object = None,
    caller_allowlist: object = None,
) -> dict[str, Any]:
    """Create a namespace id and register it for private gaze/resolve scoping."""
    slug = normalize_slug(raw_id)
    if not is_valid_slug(slug):
        raise ProvisionError("invalid_slug")
    if is_reserved_slug(slug):
        raise ProvisionError("reserved_slug")
    if get_namespace(slug) is not None:
        raise ProvisionError("duplicate_namespace")

    try:
        days = _normalize_retention_days(retention_days)
        allowlist = _normalize_caller_allowlist(caller_allowlist)
    except ProvisionError:
        raise
    record = register_namespace(slug, retention_days=days, caller_allowlist=allowlist)
    if not _catalog_has_namespace(catalog, slug):
        catalog.reload((*catalog.all(), _demo_record(slug)))
    return record.as_dict()
