"""Direct signed MCP adapter for the api-spec/upgrade constellation."""

from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .service import cancel as cancel_run
from .service import continue_run as continue_upgrade
from .service import run as run_upgrade
from .service import status as upgrade_status


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_API_SPEC_UPGRADE_PRIVATE_KEY",
        key_id_env="ORRERY_API_SPEC_UPGRADE_KEY_ID",
        default_key_id="orrery-api-spec-upgrade-1",
    )
    skill = Skill(
        "api-spec-upgrade",
        version="0.1.0",
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "run",
        description=(
            "Start a resumable api-spec/upgrade constellation run. "
            "Inputs: entries[]*, pinned profile*, optional caller_id. "
            "Runs inventory → profile pin → safe upgrade; pauses with one "
            "typed action_request when breaking/unknown/decision-required "
            "findings remain."
        ),
    )
    def run(
        entries: list[dict[str, object]],
        profile: dict[str, object],
        caller_id: str = "anonymous",
    ) -> dict[str, object]:
        return run_upgrade(
            entries,
            profile,
            caller_id=caller_id,
            skill_name=skill.name,
            skill_version=skill.version,
            key_id=skill.key_id,
            private_key=private,
        )

    @skill.tool(
        "status",
        description=(
            "Read-only checkpoint status: disposition, graph_position, "
            "outstanding action_requests, and composite when completed."
        ),
    )
    def status(run_id: str = "") -> dict[str, object]:
        return upgrade_status(run_id)

    @skill.tool(
        "continue_run",
        description=(
            "Idempotent resume for a paused upgrade run. "
            "Inputs: run_id*, request_id*, response* "
            "(decisions[] with feature_id + action approve|abort), optional caller_id. "
            "Seals validate-target + compatibility-diff + composite receipt; "
            "duplicates replay."
        ),
    )
    def continue_run(
        run_id: str,
        request_id: str,
        response: dict[str, object],
        caller_id: str = "anonymous",
    ) -> dict[str, object]:
        return continue_upgrade(
            run_id,
            request_id,
            response,
            caller_id=caller_id,
            skill_name=skill.name,
            skill_version=skill.version,
            key_id=skill.key_id,
            private_key=private,
        )

    @skill.tool(
        "cancel",
        description="Cancel a paused upgrade run (terminal cancelled disposition).",
    )
    def cancel(run_id: str, caller_id: str = "anonymous") -> dict[str, object]:
        return cancel_run(run_id, caller_id=caller_id)

    return skill
