from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import STAR_VERSION
from .service import diff as diff_tables


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_TABLE_DIFF_PRIVATE_KEY",
        key_id_env="ORRERY_TABLE_DIFF_KEY_ID",
        default_key_id="orrery-table-diff-1",
    )
    skill = Skill(
        "table-diff",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool("diff", description="Compare two bounded table snapshots using an explicit key")
    def diff(
        left: dict[str, object], right: dict[str, object], key_column: str
    ) -> dict[str, object]:
        return diff_tables(left, right, key_column)

    return skill
