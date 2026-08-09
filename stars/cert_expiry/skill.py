from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import DEFAULT_HOST, STAR_VERSION
from .service import inspect as inspect_certificate


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_CERT_EXPIRY_PRIVATE_KEY",
        key_id_env="ORRERY_CERT_EXPIRY_KEY_ID",
        default_key_id="orrery-cert-expiry-1",
    )
    skill = Skill(
        "cert-expiry",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool("inspect", description="Inspect expiry for a named allowlisted TLS host")
    def inspect(host: str = DEFAULT_HOST) -> dict[str, object]:
        return inspect_certificate(host)

    return skill
