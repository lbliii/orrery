from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .service import run as run_fresh


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_TABLE_FRESH_PRIVATE_KEY",
        key_id_env="ORRERY_TABLE_FRESH_KEY_ID",
        default_key_id="orrery-table-fresh-1",
    )
    skill = Skill(
        "table-fresh",
        version="0.1.0",
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "run",
        description=(
            "Freshen a bounded flight sample and compare it to a caller baseline. "
            "Input bundle: baseline* (object with tabular rows for table-diff). "
            "Returns signed fresh-verdict Envelope chain "
            "(dispositions: ready | not-ready | stale | blocked)."
        ),
    )
    def run(baseline: dict[str, object]) -> dict[str, object]:
        return run_fresh(baseline)

    return skill
