"""Direct signed MCP adapter for the stale-proof constellation."""

from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .service import run as run_stale_proof


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_STALE_PROOF_PRIVATE_KEY",
        key_id_env="ORRERY_STALE_PROOF_KEY_ID",
        default_key_id="orrery-stale-proof-1",
    )
    skill = Skill(
        "stale-proof",
        version="0.1.0",
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool("run", description="Seal live UTC and Python release-note digest evidence")
    def run(source_digest: str = "") -> dict[str, object]:
        return run_stale_proof(source_digest)

    return skill
