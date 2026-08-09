"""Provider-card progressive disclosure and direct-MCP canary coverage (#141)."""

from __future__ import annotations

from catalog import CATALOG
from catalog.provider import ProviderCard, qualify_direct_mcp


def _card(*, attribution: str = "Required") -> ProviderCard:
    return ProviderCard(
        publisher="Example Provider",
        endpoint="https://mcp.example.test/mcp",
        transport="streamable-http",
        connection_route="direct-mcp",
        compute_locality="provider-remote",
        authentication="OAuth",
        approval="not-required",
        write_authority="read-only",
        terms_url="https://example.test/terms",
        retention="provider terms apply",
        attribution=attribution,
        pricing="provider-priced",
    )


def test_provider_card_is_exposed_without_tool_schema(example_app) -> None:
    record = CATALOG.resolve("orrery/world-time")
    assert record is not None
    resolved = record.as_dict()
    card = resolved["provider_card"]
    assert card is not None
    assert card["connection_route"] == "direct-mcp"
    assert card["compute_locality"] == "orrery-hosted"
    assert card["tool_discovery"] == "provider_tools_list_after_selection"
    assert "tools" not in card

    hit = CATALOG.match("live utc", node="public")[0].as_dict()
    assert hit["provider_card"] is not None
    assert "tools" not in hit["provider_card"]


def test_direct_mcp_canary_keeps_provider_result_out_of_qualification_record() -> None:
    calls: list[tuple[str, object]] = []

    def provider(method: str, payload: object):
        calls.append((method, payload))
        if method == "tools/list":
            return {"tools": [{"name": "lookup", "inputSchema": {"very": "large"}}]}
        return {"content": [{"text": "provider-only content"}]}

    result = qualify_direct_mcp(
        _card(), call=provider, permitted_tool="lookup", arguments={"q": "UTC"}
    )

    assert result.status == "verified"
    assert result.tools_listed is True
    assert result.permitted_call is True
    assert result.terms_checked is True
    assert result.attribution_checked is True
    assert result.tool_count == 1
    assert "provider-only content" not in str(result.as_dict())
    assert calls == [
        ("tools/list", {}),
        ("tools/call", {"name": "lookup", "arguments": {"q": "UTC"}}),
    ]


def test_direct_mcp_canary_marks_missing_permitted_tool_degraded() -> None:
    def provider(method: str, payload: object):
        assert method == "tools/list"
        return {"tools": [{"name": "write_everything"}]}

    result = qualify_direct_mcp(_card(), call=provider, permitted_tool="lookup")

    assert result.status == "degraded"
    assert result.tools_listed is True
    assert result.permitted_call is False
    assert "lookup" in (result.detail or "")


def test_direct_mcp_canary_cannot_verify_without_attribution_requirement() -> None:
    def provider(method: str, payload: object):
        if method == "tools/list":
            return {"tools": [{"name": "lookup"}]}
        return {}

    result = qualify_direct_mcp(_card(attribution="none"), call=provider, permitted_tool="lookup")
    assert result.status == "experimental"
    assert result.attribution_checked is False
