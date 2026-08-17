"""Direct signed MCP adapter for the plugin-readiness constellation."""

from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .service import run as run_plugin_readiness


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_PLUGIN_READINESS_PRIVATE_KEY",
        key_id_env="ORRERY_PLUGIN_READINESS_KEY_ID",
        default_key_id="orrery-plugin-readiness-1",
    )
    skill = Skill(
        "plugin-readiness",
        version="0.1.0",
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "run",
        description=(
            "Assess a caller plugin bundle (Agent Plugins 1.0.0). "
            "Input: files* (array of {path, content}). "
            "Returns signed composite disposition "
            "(conformant | needs-work | inconclusive). Sync only; no pause."
        ),
    )
    def run(files: list[dict[str, object]]) -> dict[str, object]:
        return run_plugin_readiness(files)

    return skill
