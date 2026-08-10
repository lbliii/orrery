from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .service import MODE_CONTENT_BUNDLE, MODE_METADATA
from .service import run as run_check


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_SHIP_CHECK_PRIVATE_KEY",
        key_id_env="ORRERY_SHIP_CHECK_KEY_ID",
        default_key_id="orrery-ship-check-1",
    )
    skill = Skill(
        "ship-check",
        version="0.1.0",
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "run",
        description=(
            "Ship-check / content-ship-check: sealed evidence before reasoning. "
            "Modes via run input: metadata (default) — package* + optional "
            "source_digest; content-bundle — files* using content-readiness "
            "stages (manifest-bind → preflight → structure-audit → "
            "link-check-bounded → seal). Returns one composite receipt "
            "(signed-envelope-chain). Never deploy approval. Sync only."
        ),
    )
    def run(
        package: str = "",
        source_digest: str = "",
        mode: str = MODE_METADATA,
        files: list[dict[str, object]] | None = None,
        policy: str = "orrery/docs-only@v1",
        max_link_count: int = 20,
    ) -> dict[str, object]:
        # Keep positional-only call for default metadata so signing fixtures
        # that stub ``run_check(package, digest)`` remain valid.
        if mode in (MODE_METADATA, ""):
            return run_check(package, source_digest)
        return run_check(
            package,
            source_digest,
            mode=mode or MODE_CONTENT_BUNDLE,
            files=files,
            policy=policy,
            max_link_count=max_link_count,
        )

    return skill
