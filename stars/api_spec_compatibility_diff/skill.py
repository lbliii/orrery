from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import STAR_VERSION
from .service import compatibility_diff as build_diff


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_API_SPEC_COMPATIBILITY_DIFF_PRIVATE_KEY",
        key_id_env="ORRERY_API_SPEC_COMPATIBILITY_DIFF_KEY_ID",
        default_key_id="orrery-api-spec-compatibility-diff-1",
    )
    skill = Skill(
        "api-spec-compatibility-diff",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "diff",
        description=(
            "Compare source and candidate target OpenAPI specs under an ADR 0008 "
            "compatibility_policy; classify changes without claiming runtime "
            "compatibility from structural equality"
        ),
    )
    def diff(
        source_entries: list[dict[str, str]],
        target_entries: list[dict[str, str]],
        compatibility_policy: dict[str, object],
    ) -> dict[str, object]:
        return build_diff(source_entries, target_entries, compatibility_policy)

    return skill
