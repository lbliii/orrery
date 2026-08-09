from datetime import UTC, datetime

from stars.builtins import builtin_registry
from stars.ship_check.service import run
from stars.ship_check.skill import build_skill


def test_complete_and_incomplete_component_paths() -> None:
    ok = run(
        "httpx",
        "sha256:old",
        package_provider=lambda _: {"version": "1", "source_digest": "sha256:p"},
        source_provider=lambda _: {"status": "unchanged", "current_digest": "sha256:s"},
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert ok["verdict"] == "ready_to_reason" and ok["source_watch"]["status"] == "unchanged"
    bad = run(
        "zod",
        package_provider=lambda _: {"error": "down"},
        source_provider=lambda _: {"status": "changed"},
    )
    assert bad["verdict"] == "incomplete"


def test_registry_constellation_and_skill() -> None:
    definition = builtin_registry().get("orrery/ship-check")
    assert (
        definition.kind == "constellation"
        and definition.direct_mcp_path == "/constellations/ship-check/mcp"
    )
    assert {item.name for item in build_skill()._pending} == {"run"}
