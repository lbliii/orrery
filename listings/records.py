"""Project a listing document onto a Skill DNS ResolveRecord."""

from __future__ import annotations

from catalog.agent_card import AgentCard, AgentCardIO
from catalog.models import ResolveRecord
from catalog.provider import ProviderCard

from .schema import ListingDocument


def listing_card(doc: ListingDocument) -> AgentCard:
    """Minimal agent card from listing fields (not registered in AGENT_CARDS)."""
    inputs = ()
    if doc.inputs_summary:
        inputs = (AgentCardIO(name="inputs", type="object", note=doc.inputs_summary),)
    return AgentCard(
        summary=doc.summary,
        use_when=doc.use_when,
        not_for=("first-party orrery/* stars", "unverified as oracle_ok"),
        example_intents=doc.use_when[:1],
        locality="publisher-hosted",
        write_authority="publisher-defined",
        approval="not-required",
        inputs=inputs,
        outputs=(AgentCardIO(name="result", type="object"),),
        tools=doc.tools,
        coverage_href="/coverage/listings",
    )


def listing_to_record(doc: ListingDocument) -> ResolveRecord:
    """Build a newcomer resolve row (oracle_ok false, publisher-hosted)."""
    card = listing_card(doc)
    publisher = doc.desired_name.split("/", 1)[0]
    return ResolveRecord(
        name=doc.live_name,
        endpoint=doc.endpoint,
        content_digest=f"sha256:{doc.content_digest}",
        kind="star",
        visibility="public",
        description=doc.summary,
        key_id=doc.key_id,
        alg=doc.alg,
        price_per_call=doc.price_per_call,
        oracle_ok=False,
        tools=doc.tools,
        provider_card=ProviderCard(
            publisher=publisher,
            endpoint=doc.endpoint,
            transport=doc.transport,
            connection_route="direct-mcp",
            compute_locality="publisher-hosted",
            authentication="publisher-defined",
            approval="not-required",
            write_authority="publisher-defined",
            terms_url=doc.contact,
            retention="not cached by Orrery",
            attribution=publisher,
            pricing=doc.price_per_call or "free",
            health="experimental",
            tool_context_budget=min(len(doc.tools), 12),
        ),
        agent_card=card,
        index_tier="newcomer",
        claimed_name=doc.desired_name,
        listing_url=doc.listing_url,
    )
