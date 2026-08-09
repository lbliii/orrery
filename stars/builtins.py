"""Built-in Star package discovery and factory loading."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any

from ._core import StarRegistry

BUILTIN_STAR_PACKAGES = (
    "stars.html_to_pdf",
    "stars.source_watch",
    "stars.world_time",
)


def builtin_registry() -> StarRegistry:
    """Return the validated registry of Stars shipped by this Orrery host."""
    registry = StarRegistry()
    for package in BUILTIN_STAR_PACKAGES:
        registry.register_builtin(package)
    return registry


def load_factory(reference: str) -> Callable[..., Any]:
    """Resolve a manifest ``module:attribute`` factory reference."""
    module_name, separator, attribute = reference.partition(":")
    if not separator or not module_name or not attribute:
        msg = f"Expected module:attribute factory reference, got {reference!r}"
        raise ValueError(msg)
    factory = getattr(importlib.import_module(module_name), attribute)
    if not callable(factory):
        msg = f"Star factory {reference!r} is not callable"
        raise TypeError(msg)
    return factory


def build_direct_skills(
    registry: StarRegistry,
) -> dict[str, Any]:
    """Build each canonical skill used by direct per-Star MCP endpoints."""
    return {definition.name: load_factory(definition.skill_factory)() for definition in registry}
