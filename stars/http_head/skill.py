"""Signed MCP adapter for bounded HTTP metadata observations."""

from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import DEFAULT_TARGET, STAR_VERSION
from .service import head as observe_head


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_HTTP_HEAD_PRIVATE_KEY",
        key_id_env="ORRERY_HTTP_HEAD_KEY_ID",
        default_key_id="orrery-http-head-1",
    )
    skill = Skill(
        "http-head",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool("head", description="Fetch fresh metadata for an allowlisted official HTTP target")
    def head(target: str = DEFAULT_TARGET) -> dict[str, object]:
        return observe_head(target)

    return skill
