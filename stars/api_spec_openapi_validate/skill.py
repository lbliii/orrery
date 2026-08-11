from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import STAR_VERSION
from .service import validate as run_validate


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_API_SPEC_OPENAPI_VALIDATE_PRIVATE_KEY",
        key_id_env="ORRERY_API_SPEC_OPENAPI_VALIDATE_KEY_ID",
        default_key_id="orrery-api-spec-openapi-validate-1",
    )
    skill = Skill(
        "api-spec-openapi-validate",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "validate",
        description=(
            "Validate OpenAPI target bytes against a sealed change_bundle under "
            "a pinned migration profile. Schema conformance only — no runtime "
            "compatibility claim."
        ),
    )
    def validate(
        target_entries: list[dict[str, str]],
        change_bundle: dict[str, object],
        profile: dict[str, object],
        source_entries: list[dict[str, str]] | None = None,
        plan: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return run_validate(
            target_entries,
            change_bundle,
            profile,
            source_entries=source_entries,
            plan=plan,
        )

    return skill
