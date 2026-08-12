"""L4 smoke for invite-ready secretary constellation (#110)."""

from __future__ import annotations

from datetime import UTC, datetime

from catalog.constellation import policy_for
from catalog.sync import build_star_records
from stars.builtins import build_direct_skills, builtin_registry
from stars.invite_ready.service import ATLAS_RECOMMENDATION, run
from stars.invite_ready.skill import build_skill

FIXED_TIME = datetime(2026, 8, 11, 14, 0, 0, tzinfo=UTC)


def test_invite_ready_composes_complete_enrichment_for_draft_invite() -> None:
    result = run(
        place="new-york",
        venue="central-park-cafe-nyc",
        flight="AA100",
        date="2026-08-11",
        time_fetch=lambda: {"datetime": "2026-08-11T14:00:00Z", "source": "fixture"},
        flight_fetch=lambda **_: {
            "flight": "AA100",
            "date": "2026-08-11",
            "status": "on_time",
            "departure_airport": "JFK",
            "arrival_airport": "LAX",
        },
        geocode_fetch=lambda **_: {
            "place": "new-york",
            "display_name": "New York, NY",
            "latitude": 40.7128,
            "longitude": -74.0060,
        },
        hours_fetch=lambda **_: {
            "venue": "central-park-cafe-nyc",
            "display_name": "Central Park Cafe (New York)",
            "timezone": "America/New_York",
            "open_now": True,
        },
    )

    assert result["status"] == "enriched"
    assert result["enrichment"]["utc"] == "2026-08-11T14:00:00Z"
    assert result["enrichment"]["flight_status"] == "on_time"
    assert result["enrichment"]["venue_open_now"] is True
    assert result["atlas_recommendation"] == ATLAS_RECOMMENDATION
    assert "Google Maps" in result["limitations"][0]


def test_component_failure_is_explicitly_incomplete_with_full_component_evidence() -> None:
    result = run(
        time_fetch=lambda: {"error": "upstream_unreachable", "source": "clock"},
        flight_fetch=lambda **_: {"error": "flight_not_allowed", "flight": "ZZ999"},
        geocode_fetch=lambda **_: {"error": "place_not_allowed", "place": "unknown"},
        hours_fetch=lambda **_: {"error": "venue_not_allowed", "venue": "unknown"},
    )

    assert result["status"] == "incomplete"
    assert result["components"]["world_time"]["error"] == "upstream_unreachable"
    assert result["components"]["flight_status"]["error"] == "flight_not_allowed"
    assert result["components"]["geocode"]["error"] == "place_not_allowed"
    assert result["components"]["place_hours"]["error"] == "venue_not_allowed"


def test_registry_policy_and_direct_signed_skill_are_constellation_only() -> None:
    registry = builtin_registry()
    definition = registry.get("orrery/invite-ready")
    assert definition.kind == "constellation"
    assert definition.direct_mcp_path == "/constellations/invite-ready/mcp"
    assert definition.tools == ("run",)
    graph = policy_for("orrery/invite-ready")
    assert graph is not None
    assert [node.star_ref for node in graph.nodes if node.star_ref] == [
        "orrery/world-time",
        "orrery/flight-status",
        "orrery/geocode",
        "orrery/place-hours",
    ]
    record = next(
        record
        for record in build_star_records(registry, build_direct_skills(registry))
        if record.name == "orrery/invite-ready"
    )
    assert record.kind == "constellation" and record.tools == ("run",)
    envelope = next(item for item in build_skill()._pending if item.name == "run").handler()
    assert envelope.signature and envelope.payload["constellation"] == "orrery/invite-ready"
