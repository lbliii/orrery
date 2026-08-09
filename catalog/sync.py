"""Merge live publish-oracle manifests into the resolve catalog.

Public stars are built from mounted ``chirp.skill`` manifests (real digests,
versions, tools). Constellation horizon seeds stay static until Wave 4.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .fixtures import CONSTELLATION_SEEDS
from .models import ResolveRecord
from .store import replace_catalog

if TYPE_CHECKING:
    from chirp.skill.publish import PublishReceipt
    from chirp.skill.registry import SkillRegistry

#: Public callable stars on this host (Skill DNS names + copy).
PUBLIC_STAR_META: dict[str, dict[str, object]] = {
    "html-to-pdf": {
        "catalog_name": "orrery/html-to-pdf",
        "description": "Render HTML → PDF",
        "endpoint": "mcp://orrery.dev/s/html-to-pdf",
    },
    "world-time": {
        "catalog_name": "orrery/world-time",
        "description": "Live UTC at call time — offline clones are stale",
        "endpoint": "mcp://orrery.dev/s/world-time",
    },
}


def _manifest_map(registry: SkillRegistry) -> dict[str, object]:
    out: dict[str, object] = {}
    for manifest in registry.manifests():
        out[manifest.name] = manifest
    return out


def build_star_records(
    registry: SkillRegistry,
    *,
    receipt: PublishReceipt | None = None,
) -> tuple[ResolveRecord, ...]:
    """Build public star rows from mounted skills + freeze manifests."""
    manifests = _manifest_map(registry)
    if receipt is not None:
        for raw in receipt.manifests:
            name = str(raw.get("name", ""))
            if name:
                manifests[name] = raw

    records: list[ResolveRecord] = []
    for skill_name, meta in PUBLIC_STAR_META.items():
        skill = registry.get(skill_name)
        manifest = manifests.get(skill_name)
        if skill is None or manifest is None:
            continue

        if hasattr(manifest, "content_digest"):
            digest = str(manifest.content_digest)
            version = str(manifest.version)
            tools = tuple(str(t) for t in manifest.tools)
        else:
            digest = str(manifest["content_digest"])
            version = str(manifest.get("version") or skill.version)
            tools = tuple(str(t) for t in manifest.get("tools") or ())

        records.append(
            ResolveRecord(
                name=str(meta["catalog_name"]),
                version=version,
                kind="star",
                visibility="public",
                description=str(meta["description"]),
                endpoint=str(meta["endpoint"]),
                key_id=str(skill.key_id),
                content_digest=digest,
                price_per_call=None,
                oracle_ok=True,
                tools=tools or tuple(t.name for t in skill._pending),
            )
        )
    return tuple(records)


def refresh_catalog(
    registry: SkillRegistry,
    *,
    receipt: PublishReceipt | None = None,
) -> tuple[ResolveRecord, ...]:
    """Replace the process catalog with live stars + constellation seeds."""
    stars = build_star_records(registry, receipt=receipt)
    records = stars + CONSTELLATION_SEEDS

    from trust.oracle import oracle_ok_for_record

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
            oracle_ok=oracle_ok_for_record(r),
            tools=r.tools,
        )
        for r in records
    )
    replace_catalog(enriched)
    return enriched
