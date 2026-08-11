"""Signed MCP adapter for offline allowlisted venue hours lookup."""

from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import DEFAULT_VENUE, STAR_VERSION
from .service import answer as answer_place_hours
from .service import place_hours as lookup_place_hours


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_PLACE_HOURS_PRIVATE_KEY",
        key_id_env="ORRERY_PLACE_HOURS_KEY_ID",
        default_key_id="orrery-place-hours-1",
    )
    skill = Skill(
        "place-hours",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "place_hours",
        description="Resolve allowlisted venue token to hours and open-now (offline)",
    )
    def place_hours_tool(venue: str, as_of: str | None = None) -> dict[str, object]:
        return lookup_place_hours(venue=venue, as_of=as_of)

    @skill.tool("answer", description="Answer with venue hours facts sealed in an Envelope")
    def answer_tool(venue: str = DEFAULT_VENUE, as_of: str | None = None) -> dict[str, object]:
        return answer_place_hours(venue=venue, as_of=as_of)

    return skill
