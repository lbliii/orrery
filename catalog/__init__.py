"""Orrery resolve catalog — Skill DNS records and Gaze discovery."""

from .agent_card import AgentCard, AgentCardError, agent_card_json_schema, card_for
from .console_links import console_href_for
from .constellation import LAUNCH_GATE_POLICY, STALE_PROOF_POLICY, policy_for
from .coverage import (
    COVERAGE_GAPS,
    check_coverage,
    coverage_href,
    coverage_index,
    describe_coverage,
    list_coverage_stars,
    resolve_coverage,
)
from .dns import DEFAULT_MCP_HOST, mcp_host, mcp_url
from .gaze import (
    GAZE_DEFAULT_LIMIT,
    GAZE_MAX_LIMIT,
    GazeHit,
    GazeNode,
    clamp_gaze_limit,
)
from .models import ResolveRecord
from .provider import ProviderCard, QualificationResult, qualify_direct_mcp
from .store import CATALOG, Catalog

__all__ = [
    "CATALOG",
    "COVERAGE_GAPS",
    "DEFAULT_MCP_HOST",
    "GAZE_DEFAULT_LIMIT",
    "GAZE_MAX_LIMIT",
    "LAUNCH_GATE_POLICY",
    "STALE_PROOF_POLICY",
    "AgentCard",
    "AgentCardError",
    "Catalog",
    "GazeHit",
    "GazeNode",
    "ProviderCard",
    "QualificationResult",
    "ResolveRecord",
    "agent_card_json_schema",
    "card_for",
    "check_coverage",
    "clamp_gaze_limit",
    "console_href_for",
    "coverage_href",
    "coverage_index",
    "describe_coverage",
    "list_coverage_stars",
    "mcp_host",
    "mcp_url",
    "policy_for",
    "qualify_direct_mcp",
    "resolve_coverage",
]
