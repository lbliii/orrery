from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import STAR_VERSION
from .service import migrate as run_migrate


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_DOCS_FRONTMATTER_LINK_ASSET_MIGRATE_PRIVATE_KEY",
        key_id_env="ORRERY_DOCS_FRONTMATTER_LINK_ASSET_MIGRATE_KEY_ID",
        default_key_id="orrery-docs-frontmatter-link-asset-migrate-1",
    )
    skill = Skill(
        "docs-frontmatter-link-asset-migrate",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "migrate",
        description=(
            "Migrate frontmatter fields, internal links, anchors, and asset "
            "references under explicit profile rules; emit a patch and report"
        ),
    )
    def migrate(
        entries: list[dict[str, str]],
        rules: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return run_migrate(entries, rules)

    return skill
