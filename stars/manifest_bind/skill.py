from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import STAR_VERSION
from .service import bind as bind_manifest


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_MANIFEST_BIND_PRIVATE_KEY",
        key_id_env="ORRERY_MANIFEST_BIND_KEY_ID",
        default_key_id="orrery-manifest-bind-1",
    )
    skill = Skill(
        "manifest-bind",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "bind",
        description=(
            "Bind caller-supplied file path/sha256/size rows into a stable manifest_digest envelope"
        ),
    )
    def bind(files: list[dict[str, object]]) -> dict[str, object]:
        return bind_manifest(files)

    return skill
