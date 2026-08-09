"""L4 smoke for the real two-component stale-proof constellation (#88, #119)."""

from catalog.constellation import policy_for
from catalog.sync import build_star_records
from stars.builtins import build_direct_skills, builtin_registry
from stars.stale_proof.service import run
from stars.stale_proof.skill import build_skill


def test_stale_proof_composes_complete_live_evidence_without_persistence_claim() -> None:
    result = run(
        "sha256:caller-held",
        time_fetch=lambda: {"datetime": "2026-08-09T12:00:00Z", "source": "fixture"},
        diff_fetch=lambda source, digest: {
            "source": source,
            "status": "unchanged",
            "known_digest": digest,
            "current_digest": "sha256:current",
        },
    )

    assert result["status"] == "fresh_proof"
    assert result["utc"] == "2026-08-09T12:00:00Z"
    assert result["source_status"] == "unchanged"
    assert result["components"]["source_watch"]["current_digest"] == "sha256:current"
    assert "not invoked here" in result["limitations"][2]


def test_component_failure_is_explicitly_incomplete_with_full_component_evidence() -> None:
    result = run(
        time_fetch=lambda: {"error": "upstream_unreachable", "source": "clock"},
        diff_fetch=lambda source, _digest: {"source": source, "error": "upstream_unreachable"},
    )

    assert result["status"] == "incomplete"
    assert result["components"]["world_time"]["error"] == "upstream_unreachable"
    assert result["components"]["source_watch"]["error"] == "upstream_unreachable"


def test_registry_policy_and_direct_signed_skill_are_constellation_only() -> None:
    registry = builtin_registry()
    definition = registry.get("orrery/stale-proof")
    assert definition.kind == "constellation"
    assert definition.direct_mcp_path == "/constellations/stale-proof/mcp"
    assert definition.tools == ("run",)
    graph = policy_for("orrery/stale-proof")
    assert graph is not None
    assert [node.star_ref for node in graph.nodes if node.star_ref] == [
        "orrery/world-time",
        "orrery/source-watch",
    ]
    record = next(
        record
        for record in build_star_records(registry, build_direct_skills(registry))
        if record.name == "orrery/stale-proof"
    )
    assert record.kind == "constellation" and record.tools == ("run",)
    envelope = next(item for item in build_skill()._pending if item.name == "run").handler()
    assert envelope.signature and envelope.payload["constellation"] == "orrery/stale-proof"
