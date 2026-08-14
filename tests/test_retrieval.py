"""Flagged GazeRetriever merge on gaze_match (#466)."""

from __future__ import annotations

import pytest

from catalog.agent_card import AgentCard
from catalog.models import ResolveRecord
from catalog.retrieval import (
    FixedRetriever,
    LexicalGazeRetriever,
    configure_retriever,
    retrieval_enabled,
)
from catalog.store import Catalog


@pytest.fixture(autouse=True)
def _reset_retriever() -> None:
    configure_retriever(None)
    yield
    configure_retriever(None)


def _card(*, summary: str, use_when: str, intent: str) -> AgentCard:
    return AgentCard(
        summary=summary,
        use_when=(use_when,),
        not_for=("test",),
        example_intents=(intent,),
        locality="test",
        write_authority="none",
        approval="not-required",
        inputs=(),
        outputs=(),
        tools=("check",),
        coverage_href="/coverage/test",
    )


def _record(
    name: str,
    *,
    visibility: str = "public",
    description: str = "alpha helper",
    price: str | None = None,
    card: AgentCard | None = None,
) -> ResolveRecord:
    return ResolveRecord(
        name=name,
        endpoint=f"mcp://example/{name}/mcp",
        content_digest=f"sha256:{name}",
        kind="star",
        visibility=visibility,
        description=description,
        price_per_call=price,
        agent_card=card,
    )


def _catalog() -> Catalog:
    return Catalog(
        (
            _record(
                "orrery/alpha",
                description="html pdf convert helper",
                card=_card(
                    summary="convert html",
                    use_when="render html to pdf",
                    intent="html pdf",
                ),
            ),
            _record(
                "orrery/beta",
                description="zzzz",
                card=_card(
                    summary="quiet row",
                    use_when="unused blurb",
                    intent="unused phrase",
                ),
            ),
            _record(
                "acme/secret",
                visibility="private",
                description="private tenant only",
                card=_card(
                    summary="tenant secret",
                    use_when="internal only",
                    intent="secret tenant",
                ),
            ),
            _record(
                "orrery/toll-row",
                description="zzzz",
                price="$1",
                card=_card(
                    summary="toll row",
                    use_when="unused toll blurb",
                    intent="unused toll",
                ),
            ),
        )
    )


@pytest.mark.issue(466)
def test_flag_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ORRERY_GAZE_RETRIEVAL", raising=False)
    assert retrieval_enabled() is False
    monkeypatch.setenv("ORRERY_GAZE_RETRIEVAL", "0")
    assert retrieval_enabled() is False
    monkeypatch.setenv("ORRERY_GAZE_RETRIEVAL", "1")
    assert retrieval_enabled() is True


@pytest.mark.issue(466)
def test_flag_off_ignores_injected_retriever(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ORRERY_GAZE_RETRIEVAL", raising=False)
    configure_retriever(FixedRetriever(("orrery/beta", "acme/secret")))
    catalog = _catalog()
    hits = catalog.match("html pdf", node="public")
    names = [hit.name for hit in hits]
    assert "orrery/alpha" in names
    assert "orrery/beta" not in names
    assert all(not name.startswith("acme/") for name in names)
    assert isinstance(hits, tuple)


@pytest.mark.issue(466)
def test_injected_retriever_admits_in_node_name_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ORRERY_GAZE_RETRIEVAL", "1")
    configure_retriever(FixedRetriever(("orrery/beta", "acme/secret")))
    catalog = _catalog()
    hits = catalog.match("html pdf", node="public")
    names = [hit.name for hit in hits]
    assert "orrery/alpha" in names
    assert "orrery/beta" in names
    assert "acme/secret" not in names
    assert isinstance(hits, tuple)
    for hit in hits:
        wire = hit.as_dict()
        assert "winner" not in wire
        assert "best" not in wire
        assert "route" not in wire


@pytest.mark.issue(466)
def test_lexical_v1_readmits_paid_facet(monkeypatch: pytest.MonkeyPatch) -> None:
    catalog = _catalog()
    monkeypatch.delenv("ORRERY_GAZE_RETRIEVAL", raising=False)
    assert "orrery/toll-row" not in [hit.name for hit in catalog.match("paid")]
    monkeypatch.setenv("ORRERY_GAZE_RETRIEVAL", "1")
    names = [hit.name for hit in catalog.match("paid", node="public")]
    assert "orrery/toll-row" in names
    assert "acme/secret" not in names


@pytest.mark.issue(466)
def test_search_ignores_flag_and_retriever(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORRERY_GAZE_RETRIEVAL", "1")
    configure_retriever(FixedRetriever(("orrery/beta",)))
    names = [hit.name for hit in _catalog().search("html pdf", node="public")]
    assert "orrery/alpha" in names
    assert "orrery/beta" not in names


@pytest.mark.issue(466)
def test_lexical_retriever_stays_inside_given_records() -> None:
    catalog = _catalog()
    public = catalog.records_for_node("public")
    names = LexicalGazeRetriever().retrieve("paid", public)
    assert "orrery/toll-row" in names
    assert "acme/secret" not in names
