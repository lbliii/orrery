"""Namespace provisioning — private Skill DNS zones (#29 / #382)."""

from .allowlist import (
    CALLER_HEADER,
    authorize_private_namespace,
    authorize_private_record,
    caller_from_header,
    is_private_namespace_node,
    retention_days_for,
)
from .provision import ProvisionError, provision_namespace
from .store import get_namespace, list_namespaces, reset_namespace_store
from .validation import RESERVED_SLUGS, is_reserved_slug, is_valid_slug, normalize_slug

__all__ = [
    "CALLER_HEADER",
    "RESERVED_SLUGS",
    "ProvisionError",
    "authorize_private_namespace",
    "authorize_private_record",
    "caller_from_header",
    "get_namespace",
    "is_private_namespace_node",
    "is_reserved_slug",
    "is_valid_slug",
    "list_namespaces",
    "normalize_slug",
    "provision_namespace",
    "reset_namespace_store",
    "retention_days_for",
]
