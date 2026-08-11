"""Gaze discovery layer over the resolve catalog.

Gaze is progressive disclosure: agents get names, blurbs, endpoints, prices,
facets, and supply-side trust pills — not tool payloads. Hits are derived
from :class:`ResolveRecord` seeds so Gaze and Resolve share one index
(GitHub issues #22-#24, shelf epic #58 / #64-#66).

**Agent is the semantic router.** Orrery returns a bounded shortlist; the
agent (or harness) ranks, filters by facets, or re-queries. Gaze never
forces a single winner and never returns a live tool body.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .console_links import console_href_for
from .models import ResolveRecord

if TYPE_CHECKING:
    from trust.oracle import OracleView
    from trust.satisfaction import SatisfactionPillView


def _inputs_summary_for(record: ResolveRecord) -> str | None:
    from .agent_card import inputs_summary

    if record.agent_card is None:
        return None
    return inputs_summary(record.agent_card)

#: Token splitter for ``match(intent)`` / ``search(query)``.
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*", re.IGNORECASE)

#: Default blurbs when a constellation tool has no richer copy yet.
_TOOL_BLURBS: dict[str, str] = {
    "run": "Run the constellation on an input bundle",
    "status": "Get the composite receipt or in-flight chain",
    "explain_policy": "Explain gates, loops, and fan-in in plain language",
    "check": "Run the star's primary check",
    "convert": "Convert input to the star's output format",
    "health": "Probe whether the star is live",
    "fetch": "Pull live source-backed data at call time",
    "get": "Get a live reading sealed in an Envelope",
    "answer": "Answer with live truth — not a cached package",
}

#: Stars whose value is live truth at call time (Wave 1 reactive spikes).
_REACTIVE_SHORT_NAMES: frozenset[str] = frozenset({"world-time", "source-watch"})

#: Default shortlist size for ``gaze_match`` / ``gaze_search`` (#64).
GAZE_DEFAULT_LIMIT: int = 20

#: Hard ceiling for an explicit ``limit`` argument (#64).
GAZE_MAX_LIMIT: int = 100


def clamp_gaze_limit(limit: int | None = None) -> int:
    """Normalize a hit ``limit``: default ≤20, explicit raises up to ``GAZE_MAX_LIMIT``."""
    if limit is None:
        return GAZE_DEFAULT_LIMIT
    try:
        n = int(limit)
    except (TypeError, ValueError):
        return GAZE_DEFAULT_LIMIT
    if n < 1:
        return 1
    return min(n, GAZE_MAX_LIMIT)


def price_band_for(price: str | None) -> str:
    """Coarse price facet for agent-side filters (``free`` | ``paid``)."""
    return "paid" if price else "free"


def is_reactive_record(record: ResolveRecord) -> bool:
    """Whether the record is a live-at-call-time (reactive) star."""
    if record.kind != "star":
        return False
    return record.short_name in _REACTIVE_SHORT_NAMES


@dataclass(frozen=True, slots=True)
class GazeHit:
    """One progressive-disclosure discovery result."""

    name: str
    kind: str  # "star" | "constellation" | "tool"
    blurb: str
    endpoint: str | None = None
    price: str | None = None
    href: str = ""
    provider_card: dict[str, object] | None = None
    namespace: str | None = None
    reactive: bool = False
    oracle_ok: bool = False
    console_href: str = "/console"
    oracle: OracleView | None = None
    satisfaction: SatisfactionPillView | None = None
    summary: str | None = None
    use_when: tuple[str, ...] = ()
    inputs_summary: str | None = None

    @property
    def pricing_label(self) -> str:
        return self.price if self.price else "Free"

    @property
    def price_band(self) -> str:
        return price_band_for(self.price)

    def as_dict(self) -> dict[str, object]:
        """Serialize for MCP / ``/api/gaze/*`` — no tool payloads."""
        if self.oracle is not None:
            trust_oracle: dict[str, object] = self.oracle.as_dict()
        else:
            trust_oracle = {
                "ok": self.oracle_ok,
                "pill_text": "unscored",
                "pill_class": "pill-priv",
                "host_ok": False,
                "skill_ok": None,
                "reliability_label": "unscored",
            }
        if self.satisfaction is not None:
            trust_satisfaction = self.satisfaction.as_dict()
        else:
            trust_satisfaction = {"quiet": True}
        return {
            "name": self.name,
            "kind": self.kind,
            "blurb": self.blurb,
            "endpoint": self.endpoint,
            "price": self.price,
            "price_band": self.price_band,
            "href": self.href,
            "provider_card": self.provider_card,
            "namespace": self.namespace,
            "reactive": self.reactive,
            "oracle_ok": self.oracle_ok,
            "console_href": self.console_href,
            "trust": {"oracle": trust_oracle, "satisfaction": trust_satisfaction},
            "summary": self.summary,
            "use_when": list(self.use_when),
            "inputs_summary": self.inputs_summary,
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
    from trust.oracle import oracle_for
    from trust.satisfaction import satisfaction_pill_for

    toll = record.pricing_label
    blurb_source = record.resolved_description() or ""
    blurb = f"{blurb_source} · {toll}" if blurb_source else toll
    view = oracle_for(record)
    satisfaction = satisfaction_pill_for(
        star_name=record.name,
        content_digest=record.content_digest,
    )
    card = record.agent_card
    return GazeHit(
        name=record.name,
        kind=record.kind,
        blurb=blurb,
        endpoint=record.endpoint,
        price=record.price_per_call,
        href=record.href,
        provider_card=record.provider_card.as_dict() if record.provider_card else None,
        namespace=record.namespace,
        reactive=is_reactive_record(record),
        oracle_ok=record.oracle_ok,
        console_href=console_href_for(record),
        oracle=view,
        satisfaction=satisfaction,
        summary=None if card is None else card.summary,
        use_when=() if card is None else card.use_when[:3],
        inputs_summary=_inputs_summary_for(record),
    )


def tool_hit(tool: str, *, constellation: ResolveRecord) -> GazeHit:
    """A constellation-node tool entry (kind ``tool``)."""
    from trust.oracle import oracle_for
    from trust.satisfaction import satisfaction_pill_for

    view = oracle_for(constellation)
    satisfaction = satisfaction_pill_for(
        star_name=constellation.name,
        content_digest=constellation.content_digest,
    )
    return GazeHit(
        name=tool,
        kind="tool",
        blurb=_TOOL_BLURBS.get(tool, f"Tool on {constellation.name}"),
        endpoint=None,
        price=None,
        href=constellation.href,
        provider_card=None,
        namespace=constellation.namespace,
        reactive=False,
        oracle_ok=constellation.oracle_ok,
        console_href=console_href_for(constellation),
        oracle=view,
        satisfaction=satisfaction,
    )


_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "to",
        "of",
        "for",
        "and",
        "or",
        "in",
        "on",
        "at",
        "by",
        "is",
        "be",
        "as",
        "it",
        "you",
        "your",
        "with",
        "from",
        "into",
        "not",
    }
)


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(
        token
        for token in (m.group(0).lower() for m in _TOKEN_RE.finditer(text or ""))
        if len(token) >= 3 and token not in _STOPWORDS
    )


def score_record(record: ResolveRecord, tokens: tuple[str, ...]) -> int:
    """Rank a record against intent/query tokens (higher is better)."""
    if not tokens:
        return 1
    name = record.name.lower()
    short = record.short_name.lower()
    desc = (record.resolved_description() or "").lower()
    card_text = record.agent_card.searchable_text() if record.agent_card is not None else ""
    score = 0
    for token in tokens:
        if token in (short, name):
            score += 5
        elif token in name:
            score += 3
        if token in desc:
            score += 2
        if token in card_text:
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
    # Prefer cards whose example_intents / use_when literally contain the intent.
    phrase = " ".join(tokens)
    if phrase and phrase in card_text:
        score += 6
    return score
