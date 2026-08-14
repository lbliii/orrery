"""Direct signed MCP adapter for the kida-ready constellation."""

from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .service import run as run_kida_ready


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_KIDA_READY_PRIVATE_KEY",
        key_id_env="ORRERY_KIDA_READY_KEY_ID",
        default_key_id="orrery-kida-ready-1",
    )
    skill = Skill(
        "kida-ready",
        version="0.1.0",
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "run",
        description=(
            "Validate Kida templates, gate on check pass, then render to HTML. "
            "Input: templates* (array of {path, content}), data* (JSON object), "
            "optional validate_calls, strict, surface. Returns signed composite "
            "disposition (ready | needs-work | inconclusive)."
        ),
    )
    def run(
        templates: list[dict[str, object]],
        data: dict[str, object],
        validate_calls: bool = True,
        strict: bool = False,
        surface: str = "html",
    ) -> dict[str, object]:
        return run_kida_ready(
            templates,
            data,
            validate_calls=validate_calls,
            strict=strict,
            surface=surface,
        )

    return skill
