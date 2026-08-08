"""Seed resolve records mirroring the static design mocks.

These are demo fixtures for the Resolve/Star/Constellation surfaces until the
live registry (backed by ``mount_skills``) feeds real records. Values are lifted
verbatim from ``design/resolve.html``, ``design/star.html``, and
``design/constellation.html`` so the app matches the frozen ``v1-night-gold``
direction.
"""

from __future__ import annotations

from .models import ResolveRecord

SEED_RECORDS: tuple[ResolveRecord, ...] = (
    ResolveRecord(
        name="orrery/html-to-pdf",
        version="1.2.0",
        kind="star",
        visibility="public",
        description="Render HTML → PDF",
        endpoint="mcp://orrery.dev/s/html-to-pdf",
        key_id="orrery-pdf-1",
        content_digest="sha256:9f2a7c…c814",
        price_per_call="$0.02",
        oracle_ok=True,
        tools=("convert", "health"),
    ),
    ResolveRecord(
        name="orrery/world-time",
        version="0.1.0",
        kind="star",
        visibility="public",
        description="Live UTC at call time — offline clones are stale",
        endpoint="mcp://orrery.dev/s/world-time",
        key_id="orrery-world-time-1",
        content_digest="sha256:a1b2c3…d4e5",
        price_per_call="$0.03",
        oracle_ok=True,
        tools=("fetch", "get", "answer"),
    ),
    ResolveRecord(
        name="orrery/md-linkcheck",
        version="0.4.1",
        kind="star",
        visibility="public",
        description="Docs link verdict",
        endpoint="mcp://orrery.dev/s/md-linkcheck",
        key_id="orrery-linkcheck-1",
        content_digest="sha256:41bb…0e2",
        price_per_call="$0.01",
        oracle_ok=True,
        tools=("check", "health"),
    ),
    ResolveRecord(
        name="acme/release-gate",
        kind="constellation",
        visibility="private",
        description="Private constellation entry",
        endpoint="mcp://acme.orrery.dev/s/release-gate",
        key_id="acme-release-1",
        content_digest="sha256:77d0…a19",
        price_per_call=None,
        oracle_ok=True,
        tools=("run", "status", "explain_policy"),
    ),
    ResolveRecord(
        name="acme/launch-gate",
        version="2",
        kind="constellation",
        visibility="private",
        description="Ship policy graph — gates, repair loop, fan-in",
        endpoint="mcp://acme.orrery.dev/constellations/launch-gate",
        key_id="acme-release-1",
        content_digest="sha256:c0ffee…",
        price_per_call=None,
        oracle_ok=True,
        tools=("run", "status", "explain_policy"),
    ),
)
