from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import DEFAULT_MAX_LINK_COUNT, STAR_VERSION
from .service import check as check_links


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_LINK_CHECK_BOUNDED_PRIVATE_KEY",
        key_id_env="ORRERY_LINK_CHECK_BOUNDED_KEY_ID",
        default_key_id="orrery-link-check-bounded-1",
    )
    skill = Skill(
        "link-check-bounded",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "check",
        description=(
            "Check markdown/html links with max_link_count cap and allowlisted HTTPS egress"
        ),
    )
    def check(
        files: list[dict[str, object]],
        max_link_count: int = DEFAULT_MAX_LINK_COUNT,
    ) -> dict[str, object]:
        return check_links(files, max_link_count)

    return skill
