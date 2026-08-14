"""Landing — brand hero, the gaze/resolve/call story, and a live feed.

The below-fold activity strip subscribes to ``/feed`` (SSE) so every MCP
``tools/call`` against the aggregated host appears in real time.
"""

from __future__ import annotations

import sys
from typing import Any

from chirp import Page

from stars.builtins import builtin_registry


def public_capability_counts() -> tuple[int, int]:
    """Return the live direct-registry split shown on the public landing page.

    This deliberately reads the same manifests that mount public direct MCP
    endpoints, rather than the six legacy dogfood tools on the aggregate
    ``/mcp`` host. A newly shipped manifest therefore changes the count on the
    next rendered page without a parallel catalog counter to maintain.
    """
    definitions = tuple(builtin_registry())
    return (
        sum(definition.kind == "star" for definition in definitions),
        sum(definition.kind == "constellation" for definition in definitions),
    )


def _sky_vitals_snapshot() -> dict[str, Any]:
    """Read the live host store without re-importing ``app.py``."""
    for module_name in ("orrery_app_under_test", "app", "__main__"):
        host = sys.modules.get(module_name)
        if host is not None and hasattr(host, "sky_vitals"):
            return host.sky_vitals.snapshot()
    msg = "SkyVitalsStore is not wired on the running host module"
    raise RuntimeError(msg)


def get() -> Page:
    snapshot = _sky_vitals_snapshot()
    catalog = snapshot["catalog"]
    activity = snapshot["activity"]
    demand = snapshot["demand"]
    tenancy = snapshot["tenancy"]
    return Page(
        "page.html",
        "content",
        page_block_name="content",
        page_title="Orrery — skills you point at",
        footer_note="Orrery · live host",
        star_count=catalog["stars_live"],
        constellation_count=catalog["constellations_live"],
        vitals_stars_live=catalog["stars_live"],
        vitals_constellations_live=catalog["constellations_live"],
        vitals_invocations_24h=activity["invocations_24h"],
        vitals_resolves_24h=activity["resolves_24h"],
        vitals_seals_24h=activity["seals_24h"],
        vitals_useful_7d=demand["useful_7d"],
        vitals_namespaces_live=tenancy["namespaces_live"],
    )
