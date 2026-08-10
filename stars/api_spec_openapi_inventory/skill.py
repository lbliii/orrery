from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import STAR_VERSION
from .service import inventory as build_inventory


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_API_SPEC_OPENAPI_INVENTORY_PRIVATE_KEY",
        key_id_env="ORRERY_API_SPEC_OPENAPI_INVENTORY_KEY_ID",
        default_key_id="orrery-api-spec-openapi-inventory-1",
    )
    skill = Skill(
        "api-spec-openapi-inventory",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "inventory",
        description=(
            "Parse bounded OpenAPI JSON entries and emit classified findings "
            "with dialect/version and stable digests (no external $ref fetch)"
        ),
    )
    def inventory(
        entries: list[dict[str, str]],
        ref_policy: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return build_inventory(entries, ref_policy=ref_policy)

    return skill
