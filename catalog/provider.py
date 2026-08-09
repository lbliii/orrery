"""Qualification metadata for MCP providers Orrery routes to directly.

Provider cards deliberately describe a provider without mirroring its complete
tool schema into Orrery.  An agent resolves a card, chooses it, then performs
``tools/list`` against the provider endpoint itself.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ProviderCard:
    """Compact, policy-first metadata for one MCP provider."""

    publisher: str
    endpoint: str
    transport: str
    connection_route: str
    compute_locality: str
    authentication: str
    approval: str
    write_authority: str
    terms_url: str | None
    retention: str
    attribution: str
    pricing: str
    health: str = "experimental"
    tool_context_budget: int = 12

    def as_dict(self) -> dict[str, object]:
        return {
            "publisher": self.publisher,
            "endpoint": self.endpoint,
            "transport": self.transport,
            "connection_route": self.connection_route,
            "compute_locality": self.compute_locality,
            "authentication": self.authentication,
            "approval": self.approval,
            "write_authority": self.write_authority,
            "terms_url": self.terms_url,
            "retention": self.retention,
            "attribution": self.attribution,
            "pricing": self.pricing,
            "health": self.health,
            "tool_context_budget": self.tool_context_budget,
            # Tool schemas are intentionally absent: fetch them from endpoint
            # only after selecting this provider.
            "tool_discovery": "provider_tools_list_after_selection",
        }


@dataclass(frozen=True, slots=True)
class QualificationResult:
    """Non-content evidence from a narrow direct-MCP qualification canary."""

    provider: str
    endpoint: str
    status: str
    tools_listed: bool
    permitted_call: bool
    terms_checked: bool
    attribution_checked: bool
    tool_count: int = 0
    detail: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "endpoint": self.endpoint,
            "status": self.status,
            "tools_listed": self.tools_listed,
            "permitted_call": self.permitted_call,
            "terms_checked": self.terms_checked,
            "attribution_checked": self.attribution_checked,
            "tool_count": self.tool_count,
            "detail": self.detail,
        }


DirectMcpCall = Callable[[str, Mapping[str, object]], Mapping[str, Any]]


def qualify_direct_mcp(
    card: ProviderCard,
    *,
    call: DirectMcpCall,
    permitted_tool: str,
    arguments: Mapping[str, object] | None = None,
) -> QualificationResult:
    """Run a deliberately narrow canary without proxying provider content.

    ``call`` is supplied by the caller so this foundation has no HTTP client,
    cache, or result store.  The canary retains only protocol/policy outcomes;
    provider tool results must continue directly to the selected agent.
    """
    terms_checked = card.terms_url is not None
    attribution_checked = card.attribution != "none"
    try:
        listed = call("tools/list", {})
        tools = listed.get("tools", [])
        if not isinstance(tools, list):
            raise ValueError("tools/list returned no tools array")
        tool_names = {
            tool.get("name")
            for tool in tools
            if isinstance(tool, Mapping) and isinstance(tool.get("name"), str)
        }
        if permitted_tool not in tool_names:
            return QualificationResult(
                provider=card.publisher,
                endpoint=card.endpoint,
                status="degraded",
                tools_listed=True,
                permitted_call=False,
                terms_checked=terms_checked,
                attribution_checked=attribution_checked,
                tool_count=len(tools),
                detail=f"permitted tool {permitted_tool!r} was not listed",
            )
        # Do not inspect, retain, re-sign, or return the provider's result.
        call("tools/call", {"name": permitted_tool, "arguments": dict(arguments or {})})
    except (OSError, ValueError, KeyError, TypeError) as error:
        return QualificationResult(
            provider=card.publisher,
            endpoint=card.endpoint,
            status="degraded",
            tools_listed=False,
            permitted_call=False,
            terms_checked=terms_checked,
            attribution_checked=attribution_checked,
            detail=str(error),
        )
    return QualificationResult(
        provider=card.publisher,
        endpoint=card.endpoint,
        status="verified" if terms_checked and attribution_checked else "experimental",
        tools_listed=True,
        permitted_call=True,
        terms_checked=terms_checked,
        attribution_checked=attribution_checked,
        tool_count=len(tools),
    )
