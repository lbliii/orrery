from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import STAR_VERSION
from .service import validate as run_validate


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_DOCS_MDX_VALIDATE_AND_MIGRATION_DIFF_PRIVATE_KEY",
        key_id_env="ORRERY_DOCS_MDX_VALIDATE_AND_MIGRATION_DIFF_KEY_ID",
        default_key_id="orrery-docs-mdx-validate-and-migration-diff-1",
    )
    skill = Skill(
        "docs-mdx-validate-and-migration-diff",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "validate",
        description=(
            "Validate MDX targets against a sealed change_bundle and emit "
            "bounded migration-diff evidence (no runtime compatibility claim)"
        ),
    )
    def validate(
        source_entries: list[dict[str, str]],
        target_entries: list[dict[str, str]],
        change_bundle: dict[str, object],
        profile: dict[str, object],
        plan: dict[str, object] | None = None,
        link_asset_report: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return run_validate(
            source_entries,
            target_entries,
            change_bundle,
            profile,
            plan=plan,
            link_asset_report=link_asset_report,
        )

    return skill
