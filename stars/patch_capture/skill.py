from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import STAR_VERSION
from .service import capture as capture_patch


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_PATCH_CAPTURE_PRIVATE_KEY",
        key_id_env="ORRERY_PATCH_CAPTURE_KEY_ID",
        default_key_id="orrery-patch-capture-1",
    )
    skill = Skill(
        "patch-capture",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "capture",
        description=(
            "Capture patch receipt from before/after file snapshots: digest, "
            "changed paths, and line stats"
        ),
    )
    def capture(before: dict[str, object], after: dict[str, object]) -> dict[str, object]:
        return capture_patch(before, after)

    return skill
