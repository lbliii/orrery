from __future__ import annotations

from typing import Any

from chirp.skill import Skill
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from stars.managed_api import ManagedStarService, configured_managed_service


def build_skill(
    *, private_key: Any | None = None, service: ManagedStarService | None = None
) -> Skill:
    private = private_key or Ed25519PrivateKey.generate()
    skill = Skill(
        "csv-report",
        version="1.0.0",
        private_key=private,
        key_id="orrery-cpu-1",
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "submit", description="Queue a CSV report; returns only a run ID until worker completion"
    )
    def submit(rows: list[dict[str, object]], idempotency_key: str) -> dict[str, object]:
        managed = service or configured_managed_service()
        return managed.submit(
            kind="csv-report", input={"rows": rows}, idempotency_key=idempotency_key
        )

    @skill.tool("result", description="Get a queued run or its signed final receipt")
    def result(run_id: str) -> dict[str, object]:
        managed = service or configured_managed_service()
        return managed.result(run_id)

    return skill
