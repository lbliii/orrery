from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars._core.attribution import with_via
from stars.signing import public_star_signing_key

from .contract import PROFILE_V1, STAR_VERSION
from .service import check as check_plugin


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_PLUGIN_PREFLIGHT_PRIVATE_KEY",
        key_id_env="ORRERY_PLUGIN_PREFLIGHT_KEY_ID",
        default_key_id="orrery-plugin-preflight-1",
    )
    skill = Skill(
        "plugin-preflight",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "check",
        description=(
            "Preflight a caller plugin bundle against Agent Plugins 1.0.0 "
            "and return pass/fail with violation codes. Does not install "
            "or launch plugins."
        ),
    )
    def check(
        files: list[dict[str, object]],
        profile: str = PROFILE_V1,
        manifest_digest: str | None = None,
    ) -> dict[str, object]:
        result = check_plugin(files, profile, manifest_digest)
        if "error" in result:
            return result
        return with_via(dict(result))

    return skill
