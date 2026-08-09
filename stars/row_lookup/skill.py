from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import DEFAULT_DATASET, STAR_VERSION
from .service import lookup as lookup_row


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_ROW_LOOKUP_PRIVATE_KEY",
        key_id_env="ORRERY_ROW_LOOKUP_KEY_ID",
        default_key_id="orrery-row-lookup-1",
    )
    skill = Skill(
        "row-lookup",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool("lookup", description="Look up one exact origin/destination flight aggregate")
    def lookup(
        dataset: str = DEFAULT_DATASET, key: dict[str, object] | None = None
    ) -> dict[str, object]:
        return lookup_row(dataset, key)

    return skill
