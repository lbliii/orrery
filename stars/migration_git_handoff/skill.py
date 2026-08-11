from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import STAR_VERSION
from .service import handoff as run_handoff


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_MIGRATION_GIT_HANDOFF_PRIVATE_KEY",
        key_id_env="ORRERY_MIGRATION_GIT_HANDOFF_KEY_ID",
        default_key_id="orrery-migration-git-handoff-1",
    )
    skill = Skill(
        "migration-git-handoff",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "handoff",
        description=(
            "Verify a sealed migration bundle and emit a digest-only Git/PR handoff "
            "receipt (no repo credentials or merges)."
        ),
    )
    def handoff_tool(
        profile: dict[str, object],
        change_bundle: dict[str, object],
        repo_identity_policy: dict[str, object],
        checkout_root: str,
        authority: dict[str, object],
        local_validation: dict[str, object],
        branch_or_pr_ref: dict[str, object],
        sealed_validation_digest: str | None = None,
        composite_receipt_digest: str | None = None,
    ) -> dict[str, object]:
        return run_handoff(
            profile,
            change_bundle,
            repo_identity_policy,
            checkout_root,
            authority,
            local_validation,
            branch_or_pr_ref,
            sealed_validation_digest=sealed_validation_digest,
            composite_receipt_digest=composite_receipt_digest,
        )

    return skill
