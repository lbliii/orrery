from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars._core.attribution import with_via
from stars.signing import public_star_signing_key

from .contract import STAR_VERSION
from .service import check as check_templates


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_KIDA_CHECK_PRIVATE_KEY",
        key_id_env="ORRERY_KIDA_CHECK_KEY_ID",
        default_key_id="orrery-kida-check-1",
    )
    skill = Skill(
        "kida-check",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "check",
        description=(
            "Validate Kida templates for syntax and optional component call-site issues"
        ),
    )
    def check(
        templates: list[dict[str, object]],
        validate_calls: bool = True,
        strict: bool = False,
    ) -> dict[str, object]:
        result = check_templates(
            templates,
            validate_calls=validate_calls,
            strict=strict,
        )
        if "error" in result:
            return result
        return with_via(dict(result))

    return skill
