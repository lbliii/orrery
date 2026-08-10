from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import STAR_VERSION
from .service import check as check_manifest


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_MANIFEST_PREFLIGHT_PRIVATE_KEY",
        key_id_env="ORRERY_MANIFEST_PREFLIGHT_KEY_ID",
        default_key_id="orrery-manifest-preflight-1",
    )
    skill = Skill(
        "manifest-preflight",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "check",
        description=(
            "Check files before run: preflight a caller manifest against a "
            "named policy and return pass/fail with violation codes"
        ),
    )
    def check(
        files: list[dict[str, object]],
        policy: str,
        manifest_digest: str | None = None,
    ) -> dict[str, object]:
        return check_manifest(files, policy, manifest_digest)

    return skill
