"""Landing — brand hero, the gaze/resolve/call story, and a live feed.

The below-fold activity strip subscribes to ``/feed`` (SSE) so every MCP
``tools/call`` against the aggregated host appears in real time.
"""

from __future__ import annotations

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


def get() -> Page:
    star_count, constellation_count = public_capability_counts()
    return Page(
        "page.html",
        "content",
        page_block_name="content",
        page_title="Orrery — skills you point at",
        footer_note="Orrery · live host",
        star_count=star_count,
        constellation_count=constellation_count,
    )
