"""Chirp/MCP adapter for the World Time Star contract."""

from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import STAR_VERSION
from .service import answer as answer_now
from .service import fetch as fetch_now
from .service import get as get_now


def build_skill(*, private_key: Any | None = None) -> Skill:
    """Build the direct-endpoint World Time skill with canonical tool names."""
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_WORLD_TIME_PRIVATE_KEY",
        key_id_env="ORRERY_WORLD_TIME_KEY_ID",
        default_key_id="orrery-world-time-1",
    )
    skill = Skill(
        "world-time",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "fetch", description="Fetch live UTC from the public clock API (signed at call time)"
    )
    def fetch() -> dict[str, object]:
        return fetch_now()

    @skill.tool("get", description="Get the live UTC reading (same live source as fetch)")
    def get() -> dict[str, object]:
        return get_now()

    @skill.tool("answer", description="Answer with the live UTC datetime sealed in an Envelope")
    def answer() -> dict[str, object]:
        return answer_now()

    return skill
