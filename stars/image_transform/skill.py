from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.cpu_signing import cpu_signing_key
from stars.managed_api import ManagedStarService, configured_managed_service


def build_skill(
    *, private_key: Any | None = None, service: ManagedStarService | None = None
) -> Skill:
    private, key_id = cpu_signing_key(private_key=private_key)
    skill = Skill(
        "image-transform",
        version="1.0.0",
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "submit",
        description="Queue a safe PNG transform; returns only a run ID until worker completion",
    )
    def submit(color: str, idempotency_key: str) -> dict[str, object]:
        managed = service or configured_managed_service()
        return managed.submit(
            kind="image-transform", input={"color": color}, idempotency_key=idempotency_key
        )

    @skill.tool("result", description="Get a queued run or its signed final receipt")
    def result(run_id: str) -> dict[str, object]:
        managed = service or configured_managed_service()
        return managed.result(run_id)

    return skill
