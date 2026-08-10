from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import STAR_VERSION
from .service import inventory as build_inventory


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_DOCS_RST_INVENTORY_PRIVATE_KEY",
        key_id_env="ORRERY_DOCS_RST_INVENTORY_KEY_ID",
        default_key_id="orrery-docs-rst-inventory-1",
    )
    skill = Skill(
        "docs-rst-inventory",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "inventory",
        description=(
            "Parse a bounded RST/Sphinx tree and emit classified findings with "
            "stable digests"
        ),
    )
    def inventory(entries: list[dict[str, str]]) -> dict[str, object]:
        return build_inventory(entries)

    return skill
