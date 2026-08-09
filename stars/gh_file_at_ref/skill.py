from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import DEFAULT_TARGET, STAR_VERSION
from .service import get as get_file


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_GH_FILE_AT_REF_PRIVATE_KEY",
        key_id_env="ORRERY_GH_FILE_AT_REF_KEY_ID",
        default_key_id="orrery-gh-file-at-ref-1",
    )
    skill = Skill(
        "gh-file-at-ref",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool("get", description="Get a fixed GitHub file at a full commit SHA")
    def get(target: str = DEFAULT_TARGET, ref: str = "") -> dict[str, object]:
        return get_file(target, ref)

    return skill
