"""Seed resolve records for horizon features not yet backed by live skills.

Public stars are synthesized from mounted skills in :mod:`catalog.sync` after
publish-oracle freeze. Only constellations remain static until Wave 4.
"""

from __future__ import annotations

from .dns import mcp_url
from .models import ResolveRecord

CONSTELLATION_SEEDS: tuple[ResolveRecord, ...] = (
    ResolveRecord(
        name="acme/release-gate",
        kind="constellation",
        visibility="private",
        description="Run a private release-gate policy graph (demo namespace)",
        endpoint=mcp_url("/s/release-gate", namespace="acme"),
        key_id="acme-release-1",
        content_digest="sha256:77d0…a19",
        price_per_call=None,
        oracle_ok=False,
        tools=("run", "status", "explain_policy"),
    ),
    ResolveRecord(
        name="acme/launch-gate",
        version="2",
        kind="constellation",
        visibility="private",
        description="Ship a release through gates, repair loop, and fan-in",
        endpoint=mcp_url("/constellations/launch-gate", namespace="acme"),
        key_id="acme-release-1",
        content_digest="sha256:c0ffee…",
        price_per_call=None,
        oracle_ok=False,
        tools=("run", "status", "explain_policy"),
    ),
)

#: Back-compat alias — prefer :data:`CONSTELLATION_SEEDS` or live sync output.
SEED_RECORDS: tuple[ResolveRecord, ...] = CONSTELLATION_SEEDS
