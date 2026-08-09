from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import DEFAULT_DOCUMENT, STAR_VERSION
from .service import read as read_document


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_WELL_KNOWN_PRIVATE_KEY",
        key_id_env="ORRERY_WELL_KNOWN_KEY_ID",
        default_key_id="orrery-well-known-1",
    )
    skill = Skill(
        "well-known",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool("read", description="Read a bounded named official discovery document")
    def read(document: str = DEFAULT_DOCUMENT) -> dict[str, object]:
        return read_document(document)

    return skill
