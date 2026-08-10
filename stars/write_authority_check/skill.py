from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import STAR_VERSION
from .service import check as check_authority


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_WRITE_AUTHORITY_CHECK_PRIVATE_KEY",
        key_id_env="ORRERY_WRITE_AUTHORITY_CHECK_KEY_ID",
        default_key_id="orrery-write-authority-check-1",
    )
    skill = Skill(
        "write-authority-check",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "check",
        description=(
            "Verify an explicit write grant covers the intended paths; "
            "optional signed witness envelope"
        ),
    )
    def check(manifest_digest: str, authority: dict[str, object]) -> dict[str, object]:
        return check_authority(manifest_digest, authority)

    return skill
