"""Direct signed MCP adapter for the docs/migrate-to-mdx constellation."""

from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .service import cancel as cancel_run
from .service import continue_run as continue_migration
from .service import run as run_migration
from .service import status as migration_status


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_DOCS_MIGRATE_TO_MDX_PRIVATE_KEY",
        key_id_env="ORRERY_DOCS_MIGRATE_TO_MDX_KEY_ID",
        default_key_id="orrery-docs-migrate-to-mdx-1",
    )
    skill = Skill(
        "docs-migrate-to-mdx",
        version="0.1.0",
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "run",
        description=(
            "Start a resumable docs/migrate-to-mdx constellation run. "
            "Inputs: entries[]*, pinned profile*, optional caller_id. "
            "Runs inventory → profile pin → safe convert; pauses with one "
            "typed action_request when decision_required findings remain."
        ),
    )
    def run(
        entries: list[dict[str, object]],
        profile: dict[str, object],
        caller_id: str = "anonymous",
    ) -> dict[str, object]:
        return run_migration(
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
        return migration_status(run_id)

    @skill.tool(
        "continue_run",
        description=(
            "Idempotent resume for a paused migration run. "
            "Inputs: run_id*, request_id*, response* "
            "(decisions[] with feature_id + action hold|abort), optional caller_id. "
            "Seals validate-diff + composite migration receipt; duplicates replay."
        ),
    )
    def continue_run(
        run_id: str,
        request_id: str,
        response: dict[str, object],
        caller_id: str = "anonymous",
    ) -> dict[str, object]:
        return continue_migration(
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
        description="Cancel a paused migration run (terminal cancelled disposition).",
    )
    def cancel(run_id: str, caller_id: str = "anonymous") -> dict[str, object]:
        return cancel_run(run_id, caller_id=caller_id)

    return skill
