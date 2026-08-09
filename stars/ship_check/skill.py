from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .service import run as run_check


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_SHIP_CHECK_PRIVATE_KEY",
        key_id_env="ORRERY_SHIP_CHECK_KEY_ID",
        default_key_id="orrery-ship-check-1",
    )
    skill = Skill(
        "ship-check",
        version="0.1.0",
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool("run", description="Gather fixed release and freshness evidence before reasoning")
    def run(package: str, source_digest: str = "") -> dict[str, object]:
        return run_check(package, source_digest)

    return skill
