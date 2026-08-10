"""Direct signed MCP adapter for the content-readiness constellation."""

from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .service import run as run_content_readiness


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_CONTENT_READINESS_PRIVATE_KEY",
        key_id_env="ORRERY_CONTENT_READINESS_KEY_ID",
        default_key_id="orrery-content-readiness-1",
    )
    skill = Skill(
        "content-readiness",
        version="0.1.0",
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "run",
        description=(
            "Assess a caller-provided content bundle (structure + bounded links). "
            "Input bundle: files* (array of {path, content, format?}), "
            "optional policy (string), optional max_link_count (integer). "
            "Returns signed composite disposition "
            "(ready | needs-work | inconclusive). Sync only; no pause."
        ),
    )
    def run(
        files: list[dict[str, object]],
        policy: str = "orrery/docs-only@v1",
        max_link_count: int = 20,
    ) -> dict[str, object]:
        return run_content_readiness(files, policy=policy, max_link_count=max_link_count)

    return skill
