from catalog.constellation import policy_for
from stars.builtins import builtin_registry
from stars.ship_check.service import run
from stars.ship_check.skill import build_skill


def test_complete_and_incomplete_component_paths() -> None:
    ok = run(
        "httpx",
        "sha256:old",
        package_provider=lambda _: {"version": "1", "source_digest": "sha256:p"},
        source_provider=lambda _: {"status": "unchanged", "current_digest": "sha256:s"},
        world_time_provider=lambda: {"datetime": "2026-01-01T00:00:00Z", "source": "fixture"},
    )
    assert ok["verdict"] == "ready_to_reason" and ok["source_watch"]["status"] == "unchanged"
    bad = run(
        "zod",
        package_provider=lambda _: {"error": "down"},
        source_provider=lambda _: {"status": "changed"},
    )
    assert bad["verdict"] == "incomplete"
    time_bad = run(
        "httpx",
        package_provider=lambda _: {},
        source_provider=lambda _: {},
        world_time_provider=lambda: {"error": "offline"},
    )
    assert time_bad["verdict"] == "incomplete" and time_bad["utc"]["error"] == "offline"


def test_registry_constellation_and_skill() -> None:
    definition = builtin_registry().get("orrery/ship-check")
    assert (
        definition.kind == "constellation"
        and definition.direct_mcp_path == "/constellations/ship-check/mcp"
    )
    assert {item.name for item in build_skill()._pending} == {"run"}
    assert policy_for("orrery/ship-check") is not None
