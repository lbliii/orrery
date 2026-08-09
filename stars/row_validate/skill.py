from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import DEFAULT_PROFILE, STAR_VERSION
from .service import validate as validate_row


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_ROW_VALIDATE_PRIVATE_KEY",
        key_id_env="ORRERY_ROW_VALIDATE_KEY_ID",
        default_key_id="orrery-row-validate-1",
    )
    skill = Skill(
        "row-validate",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool("validate", description="Validate one row against a named static profile")
    def validate(
        profile: str = DEFAULT_PROFILE, row: dict[str, object] | None = None
    ) -> dict[str, object]:
        return validate_row(profile, row)

    return skill
