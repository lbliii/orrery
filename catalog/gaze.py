"""Gaze discovery layer over the resolve catalog.

Gaze is progressive disclosure: agents get names, blurbs, endpoints, and
prices — not tool payloads. Hits are derived from :class:`ResolveRecord`
seeds so Gaze and Resolve share one index (GitHub issues #22-#24).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import ResolveRecord

#: Token splitter for ``match(intent)`` / ``search(query)``.
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*", re.IGNORECASE)

#: Default blurbs when a constellation tool has no richer copy yet.
_TOOL_BLURBS: dict[str, str] = {
    "run": "Execute the constellation on an input bundle",
    "status": "Composite receipt / in-flight chain",
    "explain_policy": "Gates, loops, fan-in in plain language",
    "check": "Run the star's primary check",
    "convert": "Convert input to the star's output format",
    "health": "Liveness probe for the star",
    "fetch": "Pull live source-backed data at call time",
    "get": "Get a live reading sealed in an Envelope",
    "answer": "Answer with live truth (not a cached package)",
}


@dataclass(frozen=True, slots=True)
class GazeHit:
    """One progressive-disclosure discovery result."""

    name: str
    kind: str  # "star" | "constellation" | "tool"
    blurb: str
    endpoint: str | None = None
    price: str | None = None
    href: str = ""

    def as_dict(self) -> dict[str, object]:
        """Serialize for MCP / ``/api/gaze/*`` — no tool payloads."""
        return {
            "name": self.name,
            "kind": self.kind,
            "blurb": self.blurb,
            "endpoint": self.endpoint,
            "price": self.price,
            "href": self.href,
        }


@dataclass(frozen=True, slots=True)
class GazeNode:
    """A browseable gaze node (public sky, namespace, or constellation)."""

    id: str
    label: str
    url: str
    scope: str
    tools: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "label": self.label,
            "url": self.url,
            "scope": self.scope,
            "tools": list(self.tools),
        }


#: Tools exposed on public / namespace gaze nodes (unique vs resolve/star).
GAZE_NODE_TOOLS: tuple[str, ...] = (
    "gaze_match",
    "gaze_search",
    "gaze_describe",
    "gaze_list_constellations",
)


def hit_from_record(record: ResolveRecord) -> GazeHit:
    """Build a gaze hit from a resolve record (descriptions + prices only)."""
    blurb = record.description or record.short_name
    if record.price_per_call:
        if record.description:
            blurb = f"{blurb} · {record.price_per_call}"
        else:
            blurb = record.price_per_call
    return GazeHit(
        name=record.name,
        kind=record.kind,
        blurb=blurb,
        endpoint=record.endpoint,
        price=record.price_per_call,
        href=record.href,
    )


def tool_hit(tool: str, *, constellation: ResolveRecord) -> GazeHit:
    """A constellation-node tool entry (kind ``tool``)."""
    return GazeHit(
        name=tool,
        kind="tool",
        blurb=_TOOL_BLURBS.get(tool, f"Tool on {constellation.name}"),
        endpoint=None,
        price=None,
        href=constellation.href,
    )


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(m.group(0).lower() for m in _TOKEN_RE.finditer(text or ""))


def score_record(record: ResolveRecord, tokens: tuple[str, ...]) -> int:
    """Rank a record against intent/query tokens (higher is better)."""
    if not tokens:
        return 1
    name = record.name.lower()
    short = record.short_name.lower()
    desc = (record.description or "").lower()
    score = 0
    for token in tokens:
        if token in (short, name):
            score += 5
        elif token in name:
            score += 3
        if token in desc:
            score += 2
        # Light boosts for common intent vocabulary.
        if token in {"pdf", "html", "render", "convert"} and "pdf" in name:
            score += 2
        if token in {"link", "links", "docs", "markdown", "md"} and (
            "link" in name or "md" in name
        ):
            score += 2
        if token in {"time", "utc", "clock", "now", "live", "world"} and (
            "time" in name or "world" in name
        ):
            score += 2
        if token in {"gate", "ship", "release", "policy", "launch"} and (
            "gate" in name or record.kind == "constellation"
        ):
            score += 2
    return score
