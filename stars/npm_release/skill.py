from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import DEFAULT_PACKAGE, STAR_VERSION
from .service import get as get_release


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_NPM_RELEASE_PRIVATE_KEY",
        key_id_env="ORRERY_NPM_RELEASE_KEY_ID",
        default_key_id="orrery-npm-release-1",
    )
    skill = Skill(
        "npm-release",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool("get", description="Get latest metadata for a named allowlisted npm package")
    def get(package: str = DEFAULT_PACKAGE) -> dict[str, object]:
        return get_release(package)

    return skill
