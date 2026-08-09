from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import DEFAULT_LICENSE_ID, STAR_VERSION
from .service import get as get_license


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_SPDX_LICENSE_PRIVATE_KEY",
        key_id_env="ORRERY_SPDX_LICENSE_KEY_ID",
        default_key_id="orrery-spdx-license-1",
    )
    skill = Skill(
        "spdx-license",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool("get", description="Get a bounded record for a named allowlisted SPDX license")
    def get(license_id: str = DEFAULT_LICENSE_ID) -> dict[str, object]:
        return get_license(license_id)

    return skill
