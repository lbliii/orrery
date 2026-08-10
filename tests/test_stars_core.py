"""Focused tests for the framework-neutral Star package core."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

from stars._core import StarManifestError, StarRegistry
from stars._core.registry import load_star_definition


def _manifest(**overrides: str) -> str:
    sections = {
        "star": [
            'name = "orrery/source-watch"',
            'version = "1.2.3"',
            'description = "Observe a source for changes."',
            'publisher = "orrery"',
            'publisher_key_id_env = "ORRERY_SOURCE_WATCH_KEY_ID"',
            'direct_mcp_path = "/stars/source-watch/mcp"',
            'tools = ["observe", "diff"]',
            'capability_families = ["source_monitoring"]',
        ],
        "pricing": ['unit = "call"', 'price_per_call = "0.25"', 'currency = "USD"'],
        "runtime": [
            'python_package = "stars.source_watch"',
            'skill_factory = "stars.source_watch.skill:build_skill"',
        ],
        "policy": [
            'allowed_egress = ["https://example.com"]',
            'freshness = "live_at_call"',
            'redirects = "deny"',
            "max_response_bytes = 1048576",
        ],
        "receipt": ['schema_version = "1"', 'algorithm = "Ed25519"'],
        "publish": ['corpus = "stars.source_watch.corpus:CORPUS"'],
    }
    for dotted_name, value in overrides.items():
        table, field = dotted_name.split(".", maxsplit=1)
        sections[table] = [
            value if line.startswith(f"{field} =") else line for line in sections[table]
        ]
    return "\n\n".join(f"[{table}]\n" + "\n".join(lines) for table, lines in sections.items())


def test_loader_returns_immutable_definition_from_canonical_nested_manifest(tmp_path: Path) -> None:
    path = tmp_path / "star.toml"
    path.write_text(_manifest(), encoding="utf-8")

    definition = load_star_definition(path)

    assert definition.name == "orrery/source-watch"
    assert definition.version == "1.2.3"
    assert definition.description == "Observe a source for changes."
    assert definition.publisher == "orrery"
    assert definition.publisher_key_id_env == "ORRERY_SOURCE_WATCH_KEY_ID"
    assert definition.direct_mcp_path == definition.endpoint_path == "/stars/source-watch/mcp"
    assert definition.price_per_call == Decimal("0.25")
    assert definition.price_unit == "call"
    assert definition.price_currency == "USD"
    assert definition.python_package == "stars.source_watch"
    assert definition.skill_factory == "stars.source_watch.skill:build_skill"
    assert definition.execution_mode == "direct-mcp"
    assert definition.managed_cpu_workload is None
    assert definition.allowed_egress == ("https://example.com",)
    assert definition.freshness == "live_at_call"
    assert definition.redirects == "deny"
    assert definition.max_response_bytes == 1048576
    assert definition.receipt_schema_version == "1"
    assert definition.receipt_algorithm == "Ed25519"
    assert definition.publish_corpus == "stars.source_watch.corpus:CORPUS"
    assert definition.tools == ("observe", "diff")
    assert definition.capability_families == ("source_monitoring",)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            {"star.direct_mcp_path": 'direct_mcp_path = "stars/source-watch/mcp"'},
            "must start with '/'",
        ),
        ({"pricing.price_per_call": 'price_per_call = "-1"'}, "non-negative decimal"),
        (
            {"runtime.skill_factory": 'skill_factory = "stars.source_watch.skill"'},
            "module:attribute",
        ),
        ({"policy.allowed_egress": 'allowed_egress = ["https://a", "https://a"]'}, "duplicates"),
        ({"policy.max_response_bytes": "max_response_bytes = 0"}, "positive integer"),
    ],
)
def test_loader_rejects_invalid_nested_manifest(
    tmp_path: Path, overrides: dict[str, str], message: str
) -> None:
    path = tmp_path / "star.toml"
    path.write_text(_manifest(**overrides), encoding="utf-8")

    with pytest.raises(StarManifestError, match=message):
        load_star_definition(path)


def test_loader_builds_managed_cpu_workload_from_pinned_manifest(tmp_path: Path) -> None:
    manifest = _manifest().replace(
        'skill_factory = "stars.source_watch.skill:build_skill"',
        'skill_factory = "stars.source_watch.skill:build_skill"\nexecution_mode = "managed-cpu"',
    )
    manifest += """

[managed_cpu]
image_digest = "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
command = ["/app/run"]
cpu_millicores = 500
memory_bytes = 536870912
wall_time_seconds = 60
max_input_bytes = 1048576
max_output_bytes = 4194304
"""
    path = tmp_path / "star.toml"
    path.write_text(manifest, encoding="utf-8")

    definition = load_star_definition(path)

    assert definition.execution_mode == "managed-cpu"
    assert definition.managed_cpu_workload is not None
    assert definition.managed_cpu_workload.receipt_fields()["image_digest"].startswith("sha256:")


def test_registry_loads_and_registers_a_builtin_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package_root = tmp_path / "demo_star"
    package_root.mkdir()
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (package_root / "star.toml").write_text(_manifest(), encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    registry = StarRegistry()
    definition = registry.register_builtin("demo_star")

    assert registry.get("orrery/source-watch") is definition
    assert tuple(registry) == (definition,)
    assert "orrery/source-watch" in registry
    with pytest.raises(StarManifestError, match="already registered"):
        registry.register_builtin("demo_star")
    sys.modules.pop("demo_star", None)
