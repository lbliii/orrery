"""Signed MCP adapter for static public-holiday lookup."""

from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import DEFAULT_REGION, DEFAULT_YEAR, STAR_VERSION
from .service import answer as answer_holidays
from .service import list_holidays


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_HOLIDAYS_PRIVATE_KEY",
        key_id_env="ORRERY_HOLIDAYS_KEY_ID",
        default_key_id="orrery-holidays-1",
    )
    skill = Skill(
        "holidays",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "list",
        description="List public holidays for an allowlisted region code and pinned year",
    )
    def list_tool(region: str = DEFAULT_REGION, year: int = DEFAULT_YEAR) -> dict[str, object]:
        return list_holidays(region=region, year=year)

    @skill.tool("answer", description="Answer with public holiday summary sealed in an Envelope")
    def answer_tool(region: str = DEFAULT_REGION, year: int = DEFAULT_YEAR) -> dict[str, object]:
        return answer_holidays(region=region, year=year)

    return skill
