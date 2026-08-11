"""Signed MCP adapter for offline allowlisted flight status lookup."""

from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import DEFAULT_DATE, DEFAULT_FLIGHT, STAR_VERSION
from .service import answer as answer_status
from .service import status as lookup_status


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_FLIGHT_STATUS_PRIVATE_KEY",
        key_id_env="ORRERY_FLIGHT_STATUS_KEY_ID",
        default_key_id="orrery-flight-status-1",
    )
    skill = Skill(
        "flight-status",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "status",
        description="Resolve allowlisted flight id and date to status fields (offline)",
    )
    def status_tool(flight: str, date: str) -> dict[str, object]:
        return lookup_status(flight=flight, date=date)

    @skill.tool("answer", description="Answer with flight status sealed in an Envelope")
    def answer_tool(
        flight: str = DEFAULT_FLIGHT, date: str = DEFAULT_DATE
    ) -> dict[str, object]:
        return answer_status(flight=flight, date=date)

    return skill
