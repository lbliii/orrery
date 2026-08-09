from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import DEFAULT_DATASET, STAR_VERSION
from .service import get as get_dataset


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_CSV_URL_PRIVATE_KEY",
        key_id_env="ORRERY_CSV_URL_KEY_ID",
        default_key_id="orrery-csv-url-1",
    )
    skill = Skill(
        "csv-url",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool("get", description="Get bounded typed rows from a named allowlisted CSV dataset")
    def get(dataset: str = DEFAULT_DATASET) -> dict[str, object]:
        return get_dataset(dataset)

    return skill
