"""Signed MCP adapter for offline allowlisted FX as-of lookup."""

from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import DEFAULT_AS_OF, DEFAULT_PAIR, STAR_VERSION
from .service import answer as answer_fx_rate
from .service import fx_rate as lookup_fx_rate


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_FX_RATE_PRIVATE_KEY",
        key_id_env="ORRERY_FX_RATE_KEY_ID",
        default_key_id="orrery-fx-rate-1",
    )
    skill = Skill(
        "fx-rate",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "fx_rate",
        description="Look up allowlisted FX pair at pinned as-of date (offline fixtures)",
    )
    def fx_rate_tool(pair: str, as_of: str) -> dict[str, object]:
        return lookup_fx_rate(pair=pair, as_of=as_of)

    @skill.tool("answer", description="Answer with FX rate facts sealed in an Envelope")
    def answer_tool(
        pair: str = DEFAULT_PAIR,
        as_of: str = DEFAULT_AS_OF,
    ) -> dict[str, object]:
        return answer_fx_rate(pair=pair, as_of=as_of)

    return skill
