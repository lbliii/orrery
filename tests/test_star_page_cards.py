"""Star detail pages render Agent Card sections (#219)."""

from __future__ import annotations

import json

import pytest
from chirp.testing import TestClient

from catalog.agent_card import AGENT_CARDS, card_for, required_public_card_names
from catalog.star_page import (
    build_star_page_card,
    choose_example_tool,
    example_arguments_for,
    example_call_validates,
    load_tool_contracts,
)
from stars.builtins import builtin_registry


def _public_star_names() -> tuple[str, ...]:
    registry = builtin_registry()
    names: list[str] = []
    for name in required_public_card_names():
        if not name.startswith("orrery/"):
            continue
        try:
            definition = registry.get(name)
        except KeyError:
            continue
        if definition.kind == "star":
            names.append(name)
    return tuple(names)


def test_world_time_page_card_is_registry_sourced() -> None:
    card = card_for("orrery/world-time")
    assert card is not None
    page = build_star_page_card("orrery/world-time", card)
    assert page.use_when == card.use_when
    assert page.not_for == card.not_for
    assert page.inputs == card.inputs
    assert page.outputs == card.outputs
    assert page.resolve_href == "/resolve?name=orrery/world-time"
    assert page.example_tool == "answer"
    assert page.example_call == {
        "method": "tools/call",
        "params": {"name": "answer", "arguments": {}},
    }
    assert "Callable through" not in " ".join(tool.description for tool in page.tools)
    answer = next(tool for tool in page.tools if tool.name == "answer")
    assert "Envelope" in answer.description
    assert answer.schema_fragment == "#tool-answer-schema"
    assert "syntax-" in page.example_call_html
    assert "sample" in page.example_call_html
    assert json.loads(page.example_call_json) == page.example_call
    assert "syntax-" in answer.schema_html
    assert "sample" in answer.schema_html
    assert "tool-answer-schema" in answer.schema_html


def test_html_to_pdf_example_includes_required_html() -> None:
    card = card_for("orrery/html-to-pdf")
    assert card is not None
    page = build_star_page_card("orrery/html-to-pdf", card)
    assert page.example_tool == "convert"
    assert page.example_call["params"]["arguments"]["html"] == "<p>Hello from Orrery</p>"


def test_example_calls_validate_against_published_schemas() -> None:
    failures: list[str] = []
    for name in _public_star_names():
        if not example_call_validates(name):
            failures.append(name)
    assert failures == []


def test_all_public_star_cards_project_io_and_tools() -> None:
    for name in _public_star_names():
        card = AGENT_CARDS[name]
        page = build_star_page_card(name, card)
        assert page.use_when
        assert page.not_for
        assert page.tools
        assert page.example_call_json
        payload = json.loads(page.example_call_json)
        assert payload["method"] == "tools/call"
        assert payload["params"]["name"] == page.example_tool
        assert "syntax-" in page.example_call_html
        assert "sample" in page.example_call_html
        for tool in page.tools:
            assert "syntax-" in tool.schema_html
            assert "sample" in tool.schema_html
            json.loads(tool.schema_json)


def test_choose_example_tool_prefers_run_contract_entry() -> None:
    card = card_for("orrery/ship-check")
    assert card is not None
    assert choose_example_tool(card, tuple(card.tools)) == "run"


def test_load_tool_contracts_world_time() -> None:
    contracts = load_tool_contracts("orrery/world-time")
    assert set(contracts) == {"fetch", "get", "answer"}
    assert "inputSchema" in contracts["answer"]


def test_example_arguments_for_gh_file_at_ref() -> None:
    card = card_for("orrery/gh-file-at-ref")
    assert card is not None
    contracts = load_tool_contracts("orrery/gh-file-at-ref")
    args = example_arguments_for("get", contracts["get"], card)
    assert args["target"] in {"orrery-readme", "orrery-pyproject"}
    assert len(args["ref"]) == 40


@pytest.mark.issue(219)
class TestStarPageAgentCards:
    async def test_world_time_star_page_renders_agent_sections(self, example_app) -> None:
        async with TestClient(example_app) as client:
            response = await client.get("/star/orrery/world-time")
            assert response.status == 200
            body = response.text
            assert "Use this when" in body
            assert "Not for" in body
            assert "Inputs / Outputs" in body
            assert "Example" in body
            assert "tools/call" in body
            assert "answer" in body
            assert "Callable through this Star" not in body
            assert "/resolve?name=orrery/world-time" in body
            assert "Live UTC truth at call time" in body
            assert "Envelope" in body

    async def test_every_public_star_page_has_card_sections(self, example_app) -> None:
        async with TestClient(example_app) as client:
            for name in _public_star_names():
                namespace, short = name.split("/", 1)
                response = await client.get(f"/star/{namespace}/{short}")
                assert response.status == 200, name
                body = response.text
                assert "Use this when" in body, name
                assert "Not for" in body, name
                assert "Inputs / Outputs" in body or "Example" in body, name
                assert f"/resolve?name={name}" in body, name
                assert "Callable through this Star" not in body, name
                card = AGENT_CARDS[name]
                assert card.use_when[0] in body, name
