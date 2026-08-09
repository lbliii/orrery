from __future__ import annotations

import os
from typing import Any

from chirp.skill import Skill
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .contract import DEFAULT_DOCUMENT, STAR_VERSION
from .service import read as read_document


def build_skill(*, private_key: Any | None = None) -> Skill:
    raw = os.environ.get("ORRERY_WELL_KNOWN_PRIVATE_KEY", "").strip()
    private = private_key or (
        Ed25519PrivateKey.from_private_bytes(bytes.fromhex(raw))
        if raw
        else Ed25519PrivateKey.generate()
    )
    skill = Skill(
        "well-known",
        version=STAR_VERSION,
        private_key=private,
        key_id=os.environ.get("ORRERY_WELL_KNOWN_KEY_ID", "orrery-well-known-1"),
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool("read", description="Read a bounded named official discovery document")
    def read(document: str = DEFAULT_DOCUMENT) -> dict[str, object]:
        return read_document(document)

    return skill
