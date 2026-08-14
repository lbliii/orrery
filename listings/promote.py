"""Promote ``new/{slug}`` to a claimed name on sealed useful evidence."""

from __future__ import annotations

from collections.abc import Iterable

from catalog.models import ResolveRecord
from catalog.store import CATALOG, replace_catalog
from trust.satisfaction import SatisfactionRecord, get_satisfaction_store

DEFAULT_MIN_USEFUL = 100
DEFAULT_MIN_CALLERS = 10
DEFAULT_MAX_BROKEN_RATIO = 0.25


def promotion_ready(
    ratings: Iterable[SatisfactionRecord],
    *,
    star_name: str,
    content_digest: str,
    min_useful: int = DEFAULT_MIN_USEFUL,
    min_callers: int = DEFAULT_MIN_CALLERS,
    max_broken_ratio: float = DEFAULT_MAX_BROKEN_RATIO,
) -> bool:
    """True when distinct sealed useful ratings meet the ADR 0012 bar."""
    useful_callers: set[str] = set()
    useful = 0
    sealed = 0
    brokenish = 0
    digest = content_digest.lower()
    for row in ratings:
        if row.star_name != star_name:
            continue
        if row.content_digest.lower() != digest:
            continue
        if not row.envelope_id:
            continue
        sealed += 1
        if row.verdict == "useful":
            useful += 1
            if row.caller_namespace:
                useful_callers.add(row.caller_namespace)
        elif row.verdict in {"broken", "wrong-price"}:
            brokenish += 1
    if useful < min_useful or len(useful_callers) < min_callers:
        return False
    return not (sealed and (brokenish / sealed) > max_broken_ratio)


def apply_promotion(
    live_name: str,
    *,
    min_useful: int = DEFAULT_MIN_USEFUL,
    min_callers: int = DEFAULT_MIN_CALLERS,
    max_broken_ratio: float = DEFAULT_MAX_BROKEN_RATIO,
) -> ResolveRecord | None:
    """If ready, add the claimed-name row (``index_tier=registered``)."""
    current = CATALOG.get(live_name)
    if current is None or current.index_tier != "newcomer" or not current.claimed_name:
        return None
    store = get_satisfaction_store()
    ratings = store.records_for(live_name)
    if not promotion_ready(
        ratings,
        star_name=live_name,
        content_digest=current.content_digest,
        min_useful=min_useful,
        min_callers=min_callers,
        max_broken_ratio=max_broken_ratio,
    ):
        return None
    promoted = ResolveRecord(
        name=current.claimed_name,
        endpoint=current.endpoint,
        content_digest=current.content_digest,
        kind=current.kind,
        visibility=current.visibility,
        version=current.version,
        description=current.description,
        key_id=current.key_id,
        alg=current.alg,
        price_per_call=current.price_per_call,
        oracle_ok=False,
        tools=current.tools,
        provider_card=current.provider_card,
        agent_card=current.agent_card,
        capability_families=current.capability_families,
        freshness=current.freshness,
        constellation_memberships=current.constellation_memberships,
        index_tier="registered",
        claimed_name=current.claimed_name,
        listing_url=current.listing_url,
        promoted_to=None,
    )
    alias = ResolveRecord(
        name=current.name,
        endpoint=current.endpoint,
        content_digest=current.content_digest,
        kind=current.kind,
        visibility=current.visibility,
        version=current.version,
        description=current.description,
        key_id=current.key_id,
        alg=current.alg,
        price_per_call=current.price_per_call,
        oracle_ok=False,
        tools=current.tools,
        provider_card=current.provider_card,
        agent_card=current.agent_card,
        capability_families=current.capability_families,
        freshness=current.freshness,
        constellation_memberships=current.constellation_memberships,
        index_tier="newcomer",
        claimed_name=current.claimed_name,
        listing_url=current.listing_url,
        promoted_to=current.claimed_name,
    )
    kept = tuple(r for r in CATALOG.all() if r.name not in {alias.name, promoted.name})
    replace_catalog((*kept, alias, promoted))
    from .store import upsert_listing

    upsert_listing(alias, merge_catalog=False)
    upsert_listing(promoted, merge_catalog=False)
    return promoted
