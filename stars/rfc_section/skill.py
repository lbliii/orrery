from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import DEFAULT_RFC, DEFAULT_SECTION, STAR_VERSION
from .service import get as get_section


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_RFC_SECTION_PRIVATE_KEY",
        key_id_env="ORRERY_RFC_SECTION_KEY_ID",
        default_key_id="orrery-rfc-section-1",
    )
    skill = Skill(
        "rfc-section",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool("get", description="Get a bounded section from a named allowlisted RFC")
    def get(rfc: str = DEFAULT_RFC, section: str = DEFAULT_SECTION) -> dict[str, object]:
        return get_section(rfc, section)

    return skill
