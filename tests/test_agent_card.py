"""Agent Card schema, registry completeness, and progressive disclosure (#217)."""

from __future__ import annotations

import json

import pytest
from chirp.testing import TestClient

from catalog import CATALOG
from catalog.agent_card import (
    AGENT_CARDS,
    AgentCard,
    AgentCardError,
    AgentCardIO,
    agent_card_json_schema,
    assert_registry_complete,
    card_for,
    inputs_summary,
    require_card,
    required_public_card_names,
    validate_agent_card,
)
from catalog.models import ResolveRecord


def _minimal_card(**overrides: object) -> AgentCard:
    base = dict(
        summary="A test card summary.",
        use_when=("When testing agent cards",),
        not_for=("Production misuse",),
        example_intents=("test agent card",),
        locality="orrery-hosted",
        write_authority="read-only",
        approval="not-required",
        inputs=(AgentCardIO(name="q", type="string", required=True),),
        outputs=(AgentCardIO(name="envelope", type="signed-envelope"),),
        tools=("get",),
        coverage_href="/coverage/test-card",
    )
    base.update(overrides)
    return AgentCard(**base)  # type: ignore[arg-type]


def test_json_schema_declares_required_v1_fields() -> None:
    schema = agent_card_json_schema()
    assert schema["$id"].endswith("/.well-known/orrery/agent-card.schema.json")
    required = set(schema["required"])
    assert {
        "agent_card_version",
        "summary",
        "use_when",
        "not_for",
        "example_intents",
        "locality",
        "write_authority",
        "approval",
        "inputs",
        "outputs",
        "tools",
        "coverage_href",
    } <= required


def test_registry_covers_every_public_star_and_constellation() -> None:
    names = required_public_card_names()
    assert len(names) >= 22
    assert_registry_complete(names)
    for name in names:
        card = require_card(name)
        assert card.agent_card_version == "1.0"
        assert card.coverage_href.startswith("/coverage/")


def test_ci_rejects_missing_or_invalid_cards() -> None:
    with pytest.raises(AgentCardError, match="missing"):
        assert_registry_complete(("orrery/does-not-exist",))

    with pytest.raises(AgentCardError, match="summary"):
        validate_agent_card(_minimal_card(summary=""))


def test_resolve_includes_agent_card_and_description(example_app) -> None:
    record = CATALOG.resolve("orrery/gh-file-at-ref")
    assert record is not None
    assert record.agent_card is not None
    payload = record.as_dict()
    assert payload["description"] is not None
    assert payload["description"]
    card = payload["agent_card"]
    assert isinstance(card, dict)
    assert card["summary"].startswith("Fetch a public repo file")
    assert card["tools"] == ["get"]
    assert card["coverage_href"] == "/coverage/gh-file-at-ref"


def test_resolve_description_falls_back_to_card_summary() -> None:
    card = card_for("orrery/world-time")
    assert card is not None
    record = ResolveRecord(
        name="orrery/world-time",
        endpoint="mcp://x",
        content_digest="sha256:0",
        description="",
        agent_card=card,
    )
    assert record.as_dict()["description"] == card.summary


def test_gaze_match_hit_includes_preview_fields(example_app) -> None:
    hits = CATALOG.match("pinned file from github", node="public")
    assert hits
    wire = hits[0].as_dict()
    assert wire["summary"]
    assert isinstance(wire["use_when"], list)
    assert 1 <= len(wire["use_when"]) <= 3
    assert wire["inputs_summary"]
    assert "payload" not in wire
    # Full card stays on describe/resolve — not on the shortlist.
    assert "not_for" not in wire
    assert "example_intents" not in wire


def test_gaze_describe_returns_full_agent_card(example_app) -> None:
    described = CATALOG.describe("orrery/gh-file-at-ref")
    assert described["status"] == "ok"
    card = described["agent_card"]
    assert isinstance(card, dict)
    assert card["agent_card_version"] == "1.0"
    assert "not_for" in card
    assert "example_intents" in card
    assert card["inputs"]


def test_gaze_indexes_summary_use_when_and_example_intents(example_app) -> None:
    # Phrase unique to the gh-file-at-ref card example_intents / summary.
    hits = CATALOG.search("pinned file from github")
    names = {hit.name for hit in hits}
    assert "orrery/gh-file-at-ref" in names

    matched = CATALOG.match("evidence that must not drift", node="public")
    assert any(hit.name == "orrery/gh-file-at-ref" for hit in matched)


def test_inputs_summary_marks_required_fields() -> None:
    card = require_card("orrery/gh-file-at-ref")
    summary = inputs_summary(card)
    assert "target*" in summary
    assert "ref*" in summary


def test_constellation_cards_include_run_contract() -> None:
    card = require_card("acme/launch-gate")
    assert card.run_contract is not None
    assert card.run_contract["entry_tool"] == "run"
    assert card.graph_summary
    assert card.dispositions
    assert "ready" in card.dispositions
    assert card.member_stars
    assert any(m["name"] == "orrery/html-to-pdf" for m in card.member_stars)
    assert "run_contract" in card.as_dict()
    assert "dispositions" in card.as_dict()


def test_public_constellation_cards_expose_run_contract() -> None:
    for name in ("orrery/stale-proof", "orrery/ship-check", "orrery/table-fresh"):
        card = require_card(name)
        assert card.run_contract is not None
        assert card.graph_summary
        assert card.dispositions == (
            "ready",
            "not-ready",
            "stale",
            "blocked",
        )
        assert card.member_stars is not None


def test_inputs_summary_prefers_run_contract_for_constellations() -> None:
    card = require_card("orrery/ship-check")
    summary = inputs_summary(card)
    assert "package*" in summary
    assert "source_digest" in summary


def test_gaze_describe_public_constellation_includes_run_contract(example_app) -> None:
    described = CATALOG.describe("orrery/stale-proof")
    assert described["status"] == "ok"
    assert described["kind"] == "constellation"
    assert described["run_contract"]["entry_tool"] == "run"
    assert described["graph_summary"]
    assert "ready" in described["dispositions"]
    assert described["agent_card"]["run_contract"]["entry_tool"] == "run"


def test_explain_policy_aligns_with_agent_card_fields() -> None:
    from catalog.constellation_run import explain_policy

    explained = explain_policy("acme/launch-gate")
    assert explained["status"] == "ok"
    assert explained["graph_summary"]
    assert explained["input_schema"]["type"] == "object"
    assert "bundle" in explained["input_schema"]["required"]
    assert explained["dispositions"] == [
        "ready",
        "not-ready",
        "stale",
        "blocked",
    ]
    assert explained["run_contract"]["entry_tool"] == "run"
    assert any(m["name"] == "orrery/html-to-pdf" for m in explained["member_stars"])


async def test_well_known_agent_card_schema_route(example_app) -> None:
    async with TestClient(example_app) as client:
        response = await client.get("/.well-known/orrery/agent-card.schema.json")
        assert response.status == 200
        body = json.loads(response.text)
        assert body["title"] == "Orrery Agent Card"
        assert "summary" in body["properties"]


async def test_api_resolve_exposes_agent_card(example_app) -> None:
    async with TestClient(example_app) as client:
        response = await client.get("/api/resolve?name=orrery/world-time")
        assert response.status == 200
        body = json.loads(response.text)
        assert body["description"]
        assert body["agent_card"]["tools"] == ["fetch", "get", "answer"]


def test_all_registered_cards_validate() -> None:
    for name, card in AGENT_CARDS.items():
        validate_agent_card(card, name=name)
