from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import DEFAULT_TARGET, STAR_VERSION
from .service import observe as observe_release


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_GH_RELEASE_NOTES_PRIVATE_KEY",
        key_id_env="ORRERY_GH_RELEASE_NOTES_KEY_ID",
        default_key_id="orrery-gh-release-notes-1",
    )
    skill = Skill(
        "gh-release-notes",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "observe", description="Observe latest notes for a named allowlisted GitHub release"
    )
    def observe(target: str = DEFAULT_TARGET, prior_body_digest: str = "") -> dict[str, object]:
        return observe_release(target, prior_body_digest)

    return skill
