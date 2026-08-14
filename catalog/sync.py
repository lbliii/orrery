"""Generate the resolve catalog from validated first-class Star packages."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from stars._core import StarRegistry

from .dns import mcp_url
from .fixtures import CONSTELLATION_SEEDS
from .models import ResolveRecord
from .provider import ProviderCard
from .store import replace_catalog

if TYPE_CHECKING:
    from chirp.skill.publish import PublishReceipt


def _direct_endpoint(path: str) -> str:
    """Render the public direct MCP endpoint from a Star manifest path."""
    return mcp_url(path)


def build_star_records(
    stars: StarRegistry,
    direct_skills: Mapping[str, Any],
    *,
    receipt: PublishReceipt | None = None,
) -> tuple[ResolveRecord, ...]:
    """Build public records from Star manifests and their canonical direct skills."""
    from .agent_card import card_for

    _ = receipt  # The package manifest is catalog truth; aggregate smoke is trust evidence.
    records: list[ResolveRecord] = []
    for definition in stars:
        skill = direct_skills.get(definition.name)
        if skill is None:
            msg = f"No direct skill was built for Star {definition.name!r}"
            raise RuntimeError(msg)
        manifest = skill.assemble_manifest()
        price = definition.price_per_call
        records.append(
            ResolveRecord(
                name=definition.name,
                version=definition.version,
                kind=definition.kind,
                visibility="public",
                description=definition.description,
                endpoint=_direct_endpoint(definition.direct_mcp_path),
                key_id=str(skill.key_id),
                content_digest=str(manifest.content_digest),
                price_per_call=None if price.is_zero() else f"{definition.price_currency} {price}",
                oracle_ok=True,
                tools=tuple(skill.tools),
                provider_card=ProviderCard(
                    publisher=definition.publisher,
                    endpoint=_direct_endpoint(definition.direct_mcp_path),
                    transport="streamable-http",
                    connection_route="direct-mcp",
                    compute_locality="orrery-hosted",
                    authentication="none",
                    approval="not-required",
                    write_authority="read-only",
                    terms_url="https://github.com/lbliii/orrery",
                    retention="provider-defined; no external provider content cached",
                    attribution="Orrery",
                    pricing="free" if price.is_zero() else f"{definition.price_currency} {price}",
                    health="verified",
                    tool_context_budget=min(len(skill.tools), 12),
                ),
                agent_card=card_for(definition.name),
                capability_families=definition.capability_families,
                freshness=definition.freshness,
            )
        )
    return tuple(records)


def refresh_catalog(
    stars: StarRegistry,
    direct_skills: Mapping[str, Any],
    *,
    receipt: PublishReceipt | None = None,
) -> tuple[ResolveRecord, ...]:
    """Replace the process catalog with live stars + constellation seeds."""
    from listings.store import listing_records

    records = (
        build_star_records(stars, direct_skills, receipt=receipt)
        + CONSTELLATION_SEEDS
        + listing_records()
    )

    from trust.oracle import oracle_ok_for_record

    def memberships(name: str) -> tuple[str, ...]:
        from .constellation import policy_for

        return tuple(
            constellation.name
            for constellation in records
            if constellation.kind == "constellation"
            and (policy := policy_for(constellation.name)) is not None
            and any(node.star_ref == name for node in policy.nodes)
        )

    enriched = tuple(
        ResolveRecord(
            name=r.name,
            endpoint=r.endpoint,
            content_digest=r.content_digest,
            kind=r.kind,
            visibility=r.visibility,
            version=r.version,
            description=r.description,
            key_id=r.key_id,
            alg=r.alg,
            price_per_call=r.price_per_call,
            oracle_ok=False if r.index_tier else oracle_ok_for_record(r),
            tools=r.tools,
            provider_card=r.provider_card,
            agent_card=r.agent_card,
            capability_families=r.capability_families,
            freshness=r.freshness,
            constellation_memberships=memberships(r.name) if r.kind == "star" else (),
            index_tier=r.index_tier,
            claimed_name=r.claimed_name,
            listing_url=r.listing_url,
            promoted_to=r.promoted_to,
        )
        for r in records
    )
    replace_catalog(enriched)
    return enriched
