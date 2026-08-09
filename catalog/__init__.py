"""Orrery resolve catalog — Skill DNS records and Gaze discovery."""

from .console_links import console_href_for
from .constellation import LAUNCH_GATE_POLICY, STALE_PROOF_POLICY, policy_for
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
    "DEFAULT_MCP_HOST",
    "GAZE_DEFAULT_LIMIT",
    "GAZE_MAX_LIMIT",
    "LAUNCH_GATE_POLICY",
    "STALE_PROOF_POLICY",
    "Catalog",
    "GazeHit",
    "GazeNode",
    "ProviderCard",
    "QualificationResult",
    "ResolveRecord",
    "clamp_gaze_limit",
    "console_href_for",
    "mcp_host",
    "mcp_url",
    "policy_for",
    "qualify_direct_mcp",
]
