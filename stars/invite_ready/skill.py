"""Direct signed MCP adapter for the invite-ready constellation."""

from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.flight_status.contract import DEFAULT_DATE, DEFAULT_FLIGHT
from stars.geocode.contract import DEFAULT_PLACE
from stars.place_hours.contract import DEFAULT_VENUE
from stars.signing import public_star_signing_key

from .service import run as run_invite_ready


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_INVITE_READY_PRIVATE_KEY",
        key_id_env="ORRERY_INVITE_READY_KEY_ID",
        default_key_id="orrery-invite-ready-1",
    )
    skill = Skill(
        "invite-ready",
        version="0.1.0",
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "run",
        description=(
            "Enrich a draft invite with clock, flight status, geocode, and venue hours. "
            "Input bundle: optional place, venue, flight, date (allowlisted fixtures). "
            "Returns signed composite enrichment Envelope "
            "(dispositions: enriched | incomplete)."
        ),
    )
    def run(
        place: str = DEFAULT_PLACE,
        venue: str = DEFAULT_VENUE,
        flight: str = DEFAULT_FLIGHT,
        date: str = DEFAULT_DATE,
    ) -> dict[str, object]:
        return run_invite_ready(
            place=place,
            venue=venue,
            flight=flight,
            date=date,
        )

    return skill
