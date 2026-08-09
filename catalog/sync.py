"""Generate the resolve catalog from validated first-class Star packages."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from stars._core import StarRegistry

from .dns import mcp_url
from .fixtures import CONSTELLATION_SEEDS
from .models import ResolveRecord
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
                kind="star",
                visibility="public",
                description=definition.description,
                endpoint=_direct_endpoint(definition.direct_mcp_path),
                key_id=str(skill.key_id),
                content_digest=str(manifest.content_digest),
                price_per_call=None if price.is_zero() else f"{definition.price_currency} {price}",
                oracle_ok=True,
                tools=tuple(skill.tools),
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
    records = build_star_records(stars, direct_skills, receipt=receipt) + CONSTELLATION_SEEDS

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
