"""Optional namespaced gaze retrieval (ADR 0005 / #466).

Flag ``ORRERY_GAZE_RETRIEVAL=1`` merges candidate names into ``gaze_match``.
Default off. Candidates only — never a winner API.
"""

from __future__ import annotations

import os
from typing import Protocol

from .gaze import _tokens, is_reactive_record, price_band_for
from .models import ResolveRecord

RETRIEVAL_ENV = "ORRERY_GAZE_RETRIEVAL"


class GazeRetriever(Protocol):
    def retrieve(
        self, intent: str, records: tuple[ResolveRecord, ...]
    ) -> tuple[str, ...]:
        """Candidate names only. Empty is fine. Never a winner API."""


_injected: GazeRetriever | None = None


def retrieval_enabled() -> bool:
    """True only when ``ORRERY_GAZE_RETRIEVAL=1``."""
    return os.environ.get(RETRIEVAL_ENV, "").strip() == "1"


def configure_retriever(retriever: GazeRetriever | None) -> None:
    """Tests inject a retriever; ``None`` restores the lexical v1 adapter."""
    global _injected
    _injected = retriever


def active_retriever() -> GazeRetriever:
    """Injected retriever, or the in-process lexical adapter."""
    return _injected if _injected is not None else LexicalGazeRetriever()


class LexicalGazeRetriever:
    """Re-admit in-node names when a blurb line or facet shares a token."""

    def retrieve(
        self, intent: str, records: tuple[ResolveRecord, ...]
    ) -> tuple[str, ...]:
        intent_tokens = set(_tokens(intent))
        if not intent_tokens:
            return ()
        names: list[str] = []
        for record in records:
            if intent_tokens & _index_tokens(record):
                names.append(record.name)
        return tuple(names)


def _index_tokens(record: ResolveRecord) -> set[str]:
    """Tokens from summary / use_when / example_intents / coarse facets."""
    lines: list[str] = [record.kind, price_band_for(record.price_per_call)]
    if record.oracle_ok:
        lines.append("oracle")
    if is_reactive_record(record):
        lines.append("reactive")
    card = record.agent_card
    if card is not None:
        if card.summary:
            lines.append(card.summary)
        lines.extend(card.use_when)
        lines.extend(card.example_intents)
    tokens: set[str] = set()
    for line in lines:
        tokens.update(_tokens(line))
    return tokens


class FixedRetriever:
    """Test double: always return these names (caller scopes the catalog)."""

    def __init__(self, names: tuple[str, ...]) -> None:
        self._names = names

    def retrieve(
        self, intent: str, records: tuple[ResolveRecord, ...]
    ) -> tuple[str, ...]:
        del intent, records
        return self._names
