"""Built-in Star package discovery and factory loading."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any

from ._core import StarRegistry

BUILTIN_STAR_PACKAGES = (
    "stars.html_to_pdf",
    "stars.csv_report",
    "stars.image_transform",
    "stars.http_head",
    "stars.well_known",
    "stars.cert_expiry",
    "stars.rfc_section",
    "stars.pep_section",
    "stars.spdx_license",
    "stars.csv_url",
    "stars.table_diff",
    "stars.row_lookup",
    "stars.row_validate",
    "stars.table_fresh",
    "stars.pypi_release",
    "stars.npm_release",
    "stars.gh_file_at_ref",
    "stars.gh_release_notes",
    "stars.ship_check",
    "stars.source_watch",
    "stars.stale_proof",
    "stars.content_readiness",
    "stars.authorized_content_patch",
    "stars.publish_gate",
    "stars.board_memo",
    "stars.docs_migrate_to_mdx",
    "stars.api_spec_upgrade",
    "stars.world_time",
    "stars.tz_resolve",
    "stars.geocode",
    "stars.holidays",
    "stars.decision_bind",
    "stars.manifest_bind",
    "stars.manifest_preflight",
    "stars.patch_capture",
    "stars.write_authority_check",
    "stars.migration_git_handoff",
    "stars.link_check_bounded",
    "stars.structure_audit",
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
