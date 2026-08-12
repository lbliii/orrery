"""Signed MCP adapter for offline tax-jurisdiction shape validation."""

from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import DEFAULT_PROFILE, STAR_VERSION
from .service import validate as validate_jurisdiction


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_TAX_REGION_PRIVATE_KEY",
        key_id_env="ORRERY_TAX_REGION_KEY_ID",
        default_key_id="orrery-tax-region-1",
    )
    skill = Skill(
        "tax-region",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "validate",
        description="Validate one tax-jurisdiction record against a named static profile",
    )
    def validate(
        profile: str = DEFAULT_PROFILE,
        jurisdiction: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return validate_jurisdiction(profile, jurisdiction)

    return skill
