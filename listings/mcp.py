"""Slim ``/mcp`` tools for opt-in listing ingest and rate-after-verify."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from chirp.skill import Skill

from trust.satisfaction import submit_rate

from .ping import ping_listing
from .schema import ListingError


def build_listing_skill(
    *,
    private_key: Any | None = None,
    verify_receipt: Callable[[dict[str, Any]], bool] | None = None,
    fetch: Callable[[str], bytes] | None = None,
) -> Skill:
    """MCP skill exposing ``index_ping`` and ``rate_listing`` (ADR 0012)."""
    import os

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    def _load_key(env_name: str) -> Ed25519PrivateKey:
        raw = os.environ.get(env_name, "").strip()
        if raw:
            return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(raw))
        return Ed25519PrivateKey.generate()

    private = private_key or _load_key("ORRERY_LISTING_PRIVATE_KEY")
    public = private.public_key().public_bytes_raw()
    skill = Skill(
        "listings",
        version="1.0.0",
        private_key=private,
        key_id=os.environ.get("ORRERY_LISTING_KEY_ID", "listings-1"),
        public_key=public,
    )

    @skill.tool(
        "index_ping",
        description=(
            "Submit one HTTPS orrery-listing/0.1 URL. Orrery fetches that URL "
            "only and lands the row in new/{slug} (index_tier=newcomer)."
        ),
    )
    def index_ping(url: str) -> dict[str, object]:
        try:
            record = ping_listing(url, fetch=fetch)
        except ListingError as exc:
            return {
                "status": "error",
                "error": {"code": exc.code, "message": str(exc)},
            }
        return {
            "status": "ok",
            "name": record.name,
            "claimed_name": record.claimed_name,
            "index_tier": record.index_tier,
            "endpoint": record.endpoint,
            "oracle_ok": record.oracle_ok,
        }

    @skill.tool(
        "rate_listing",
        description=(
            "After you seal a newcomer call, rate useful | stale | broken | "
            "wrong-price. Envelope-gated; optional 280-char note. No essays."
        ),
    )
    def rate_listing(
        star_name: str,
        content_digest: str,
        verdict: str,
        envelope_id: str = "",
        call_attempt_id: str = "",
        note: str = "",
        caller_namespace: str = "",
        receipt: dict[str, Any] | None = None,
    ) -> dict[str, object]:
        return submit_rate(
            star_name=star_name,
            content_digest=content_digest,
            verdict=verdict,
            envelope_id=envelope_id,
            call_attempt_id=call_attempt_id,
            note=note,
            caller_namespace=caller_namespace,
            receipt=receipt,
            verify_receipt=verify_receipt,
        )

    return skill
