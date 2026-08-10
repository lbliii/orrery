"""Direct signed MCP adapter for the authorized-content-patch constellation."""

from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .service import run as run_authorized_content_patch


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_AUTHORIZED_CONTENT_PATCH_PRIVATE_KEY",
        key_id_env="ORRERY_AUTHORIZED_CONTENT_PATCH_KEY_ID",
        default_key_id="orrery-authorized-content-patch-1",
    )
    skill = Skill(
        "authorized-content-patch",
        version="0.1.0",
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "run",
        description=(
            "Governed content edit path: readiness gates → write-authority-check → "
            "patch-capture → composite seal. Inputs: before* and after* "
            "(arrays of {path, content, format?}), authority* "
            "(policy, allowed_paths, grant_digest, optional witness), "
            "optional policy / max_link_count. Returns signed disposition "
            "(authorized | denied | needs-work | inconclusive). "
            "Does not apply patches to the caller filesystem. Sync only."
        ),
    )
    def run(
        before: list[dict[str, object]],
        after: list[dict[str, object]],
        authority: dict[str, object],
        policy: str = "orrery/docs-only@v1",
        max_link_count: int = 20,
    ) -> dict[str, object]:
        return run_authorized_content_patch(
            before,
            after,
            authority,
            policy=policy,
            max_link_count=max_link_count,
        )

    return skill
