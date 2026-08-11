"""Signed MCP adapter for offline allowlisted place geocoding."""

from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import DEFAULT_PLACE, STAR_VERSION
from .service import answer as answer_geocode
from .service import geocode as geocode_place


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_GEOCODE_PRIVATE_KEY",
        key_id_env="ORRERY_GEOCODE_KEY_ID",
        default_key_id="orrery-geocode-1",
    )
    skill = Skill(
        "geocode",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "geocode",
        description="Resolve allowlisted place token to coordinates and display name (offline)",
    )
    def geocode(place: str) -> dict[str, object]:
        return geocode_place(place=place)

    @skill.tool("answer", description="Answer with geocode facts sealed in an Envelope")
    def answer(place: str = DEFAULT_PLACE) -> dict[str, object]:
        return answer_geocode(place=place)

    return skill
