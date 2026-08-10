from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import STAR_VERSION
from .service import audit as audit_structure


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_STRUCTURE_AUDIT_PRIVATE_KEY",
        key_id_env="ORRERY_STRUCTURE_AUDIT_KEY_ID",
        default_key_id="orrery-structure-audit-1",
    )
    skill = Skill(
        "structure-audit",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "audit",
        description=(
            "Audit markdown files for heading gaps, frontmatter errors, and orphan pages"
        ),
    )
    def audit(files: list[dict[str, object]]) -> dict[str, object]:
        return audit_structure(files)

    return skill
