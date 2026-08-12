from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import STAR_VERSION
from .service import bind as bind_acceptance


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_ACCEPTANCE_BIND_PRIVATE_KEY",
        key_id_env="ORRERY_ACCEPTANCE_BIND_KEY_ID",
        default_key_id="orrery-acceptance-bind-1",
    )
    skill = Skill(
        "acceptance-bind",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "bind",
        description=(
            "Seal sprint done-criteria into a citeable AcceptanceReceipt envelope"
        ),
    )
    def bind(
        acceptance_id: str,
        criteria: list[dict[str, object]],
        adr_url: str | None = None,
        issue_url: str | None = None,
    ) -> dict[str, object]:
        return bind_acceptance(acceptance_id, criteria, adr_url, issue_url)

    return skill
