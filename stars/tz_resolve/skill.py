"""Signed MCP adapter for offline timezone resolution."""

from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import DEFAULT_PLACE, STAR_VERSION
from .service import answer as answer_timezone
from .service import resolve as resolve_timezone


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_TZ_RESOLVE_PRIVATE_KEY",
        key_id_env="ORRERY_TZ_RESOLVE_KEY_ID",
        default_key_id="orrery-tz-resolve-1",
    )
    skill = Skill(
        "tz-resolve",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "resolve",
        description="Resolve allowlisted place or lat/lon to an IANA timezone (offline)",
    )
    def resolve(
        place: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> dict[str, object]:
        return resolve_timezone(place=place, latitude=latitude, longitude=longitude)

    @skill.tool("answer", description="Answer with IANA timezone sealed in an Envelope")
    def answer(place: str = DEFAULT_PLACE) -> dict[str, object]:
        return answer_timezone(place=place)

    return skill
