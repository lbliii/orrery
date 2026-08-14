from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars._core.attribution import with_via
from stars.signing import public_star_signing_key

from .contract import STAR_VERSION
from .service import render as render_template


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_KIDA_RENDER_PRIVATE_KEY",
        key_id_env="ORRERY_KIDA_RENDER_KEY_ID",
        default_key_id="orrery-kida-render-1",
    )
    skill = Skill(
        "kida-render",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "render",
        description=(
            "Render caller-supplied Kida template bytes with JSON data to HTML "
            "and return stable digests"
        ),
    )
    def render(
        template: str | dict[str, object] | list[dict[str, object]],
        data: dict[str, object],
        surface: str = "html",
    ) -> dict[str, object]:
        result = render_template(template, data, surface=surface)
        if "error" in result:
            return result
        return with_via(dict(result))

    return skill
