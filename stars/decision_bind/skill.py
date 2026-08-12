from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars._core.attribution import with_via
from stars.signing import public_star_signing_key

from .contract import STAR_VERSION
from .service import bind as bind_decision


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_DECISION_BIND_PRIVATE_KEY",
        key_id_env="ORRERY_DECISION_BIND_KEY_ID",
        default_key_id="orrery-decision-bind-1",
    )
    skill = Skill(
        "decision-bind",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "bind",
        description="Seal a planner decision into a citeable DecisionReceipt envelope",
    )
    def bind(
        decision_id: str,
        statement: str,
        adr_url: str | None = None,
        issue_url: str | None = None,
    ) -> dict[str, object]:
        result = bind_decision(decision_id, statement, adr_url, issue_url)
        if "error" in result:
            return result
        return with_via(dict(result))

    return skill
