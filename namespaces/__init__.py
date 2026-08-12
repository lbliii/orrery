"""Namespace provisioning — private Skill DNS zones (#29 / #382)."""

from .provision import ProvisionError, provision_namespace
from .store import get_namespace, list_namespaces, reset_namespace_store
from .validation import RESERVED_SLUGS, is_reserved_slug, is_valid_slug, normalize_slug

__all__ = [
    "RESERVED_SLUGS",
    "ProvisionError",
    "get_namespace",
    "is_reserved_slug",
    "is_valid_slug",
    "list_namespaces",
    "normalize_slug",
    "provision_namespace",
    "reset_namespace_store",
]
