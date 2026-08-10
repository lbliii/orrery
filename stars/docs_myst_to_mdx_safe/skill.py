from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import STAR_VERSION
from .service import apply as apply_plan
from .service import plan as build_plan


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_DOCS_MYST_TO_MDX_SAFE_PRIVATE_KEY",
        key_id_env="ORRERY_DOCS_MYST_TO_MDX_SAFE_KEY_ID",
        default_key_id="orrery-docs-myst-to-mdx-safe-1",
    )
    skill = Skill(
        "docs-myst-to-mdx-safe",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "plan",
        description=(
            "Plan a corpus-backed safe MyST→MDX transform with hold ops for "
            "unsupported constructs"
        ),
    )
    def plan(entries: list[dict[str, str]], profile: dict[str, object]) -> dict[str, object]:
        return build_plan(entries, profile)

    @skill.tool(
        "apply",
        description=(
            "Apply a sealed MyST→MDX plan and return a change_bundle plus "
            "targets without mutating a checkout"
        ),
    )
    def apply(
        entries: list[dict[str, str]],
        plan: dict[str, object],
        profile: dict[str, object],
    ) -> dict[str, object]:
        return apply_plan(entries, plan, profile)

    return skill
