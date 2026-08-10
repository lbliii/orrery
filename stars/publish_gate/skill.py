"""Direct signed MCP adapter for the publish-gate constellation."""

from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .service import run as run_publish_gate


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_PUBLISH_GATE_PRIVATE_KEY",
        key_id_env="ORRERY_PUBLISH_GATE_KEY_ID",
        default_key_id="orrery-publish-gate-1",
    )
    skill = Skill(
        "publish-gate",
        version="0.1.0",
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "run",
        description=(
            "Publication-authority seam (two-phase after authorized-content-patch): "
            "prior artifact envelope → publish-profile write-authority → optional "
            "human witness → release seal. Inputs: prior_envelope* (Chirp wire), "
            "authority* (profile=publish, policy, allowed_paths, grant_digest, "
            "optional witness), optional prior_public_key / require_witness. "
            "Returns signed disposition "
            "(released | denied | awaiting_witness | inconclusive). "
            "Does not git push or deploy pages. Authority seam + seal only."
        ),
    )
    def run(
        prior_envelope: dict[str, object],
        authority: dict[str, object],
        prior_public_key: str | None = None,
        require_witness: bool = False,
    ) -> dict[str, object]:
        return run_publish_gate(
            prior_envelope,
            authority,
            prior_public_key=prior_public_key,
            require_witness=require_witness,
        )

    return skill
