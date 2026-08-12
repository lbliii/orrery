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


def provision_namespace(
    raw_id: str,
    *,
    catalog: Catalog,
) -> dict[str, Any]:
    """Create a namespace id and register it for private gaze/resolve scoping."""
    slug = normalize_slug(raw_id)
    if not is_valid_slug(slug):
        raise ProvisionError("invalid_slug")
    if is_reserved_slug(slug):
        raise ProvisionError("reserved_slug")
    if get_namespace(slug) is not None:
        raise ProvisionError("duplicate_namespace")

    record = register_namespace(slug)
    if not _catalog_has_namespace(catalog, slug):
        catalog.reload((*catalog.all(), _demo_record(slug)))
    return record.as_dict()
