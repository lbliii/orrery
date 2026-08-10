"""Contracts for projecting Star manifest metadata into the resolve catalog."""

from __future__ import annotations

from types import SimpleNamespace

from catalog import CATALOG
from catalog.store import replace_catalog
from catalog.sync import build_star_records, refresh_catalog
from stars._core import StarDefinition, StarRegistry


class _DirectSkill:
    """Small stand-in for the mounted direct skill used by catalog sync."""

    key_id = "test-key"
    tools = ("observe",)

    @staticmethod
    def assemble_manifest() -> SimpleNamespace:
        return SimpleNamespace(content_digest="sha256:catalog-sync-test")


def _registry() -> StarRegistry:
    definition = StarDefinition.from_manifest(
        {
            "star": {
                "name": "orrery/catalog-sync-test",
                "version": "1.0.0",
                "description": "A catalog projection test Star.",
                "publisher": "orrery",
                "publisher_key_id_env": "ORRERY_TEST_KEY_ID",
                "direct_mcp_path": "/stars/catalog-sync-test/mcp",
                "tools": ["observe"],
                "capability_families": ["source_monitoring"],
            },
            "pricing": {"price_per_call": "0", "unit": "call", "currency": "USD"},
            "runtime": {
                "python_package": "stars.catalog_sync_test",
                "skill_factory": "stars.catalog_sync_test.skill:build_skill",
            },
            "policy": {
                "allowed_egress": [],
                "freshness": "live_at_call",
                "redirects": "deny",
                "max_response_bytes": 1024,
            },
            "receipt": {"schema_version": "1", "algorithm": "Ed25519"},
            "publish": {"corpus": "stars.catalog_sync_test.corpus:CORPUS"},
        }
    )
    registry = StarRegistry()
    registry.register(definition)
    return registry


def test_build_star_records_projects_taxonomy_and_freshness_from_manifest() -> None:
    registry = _registry()

    (record,) = build_star_records(registry, {"orrery/catalog-sync-test": _DirectSkill()})

    assert record.capability_families == ("source_monitoring",)
    assert record.freshness == "live_at_call"
    assert record.as_dict()["capability_families"] == ["source_monitoring"]
    assert record.as_dict()["freshness"] == "live_at_call"


def test_refresh_catalog_preserves_taxonomy_and_freshness_after_oracle_enrichment() -> None:
    original_records = CATALOG.all()
    registry = _registry()
    try:
        records = refresh_catalog(registry, {"orrery/catalog-sync-test": _DirectSkill()})
        record = next(record for record in records if record.name == "orrery/catalog-sync-test")
        refreshed = CATALOG.get("orrery/catalog-sync-test")

        assert record.capability_families == ("source_monitoring",)
        assert record.freshness == "live_at_call"
        assert refreshed is not None
        assert refreshed.capability_families == record.capability_families
        assert refreshed.freshness == record.freshness
    finally:
        replace_catalog(original_records)
