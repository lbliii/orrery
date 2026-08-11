"""Direct signed MCP adapter for the board-memo constellation."""

from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .service import cancel as cancel_run
from .service import continue_run as continue_board_memo
from .service import run as run_board_memo
from .service import status as board_memo_status


def build_skill(*, private_key: Any | None = None) -> Skill:
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_BOARD_MEMO_PRIVATE_KEY",
        key_id_env="ORRERY_BOARD_MEMO_KEY_ID",
        default_key_id="orrery-board-memo-1",
    )
    skill = Skill(
        "board-memo",
        version="0.1.0",
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "run",
        description=(
            "Start a resumable board-memo constellation run. "
            "Inputs: title*, summary*, optional author, optional caller_id. "
            "Pauses at audience-choice with exactly one typed action_request "
            "(audience + recommendation). Does not hold a worker lease while waiting."
        ),
    )
    def run(
        title: str,
        summary: str,
        author: str = "",
        caller_id: str = "anonymous",
    ) -> dict[str, object]:
        return run_board_memo(
            title,
            summary,
            author=author,
            caller_id=caller_id,
            skill_name=skill.name,
            skill_version=skill.version,
            key_id=skill.key_id,
            private_key=private,
        )

    @skill.tool(
        "status",
        description=(
            "Read-only checkpoint status for a board-memo run: disposition, "
            "graph_position, and outstanding action_requests."
        ),
    )
    def status(run_id: str = "") -> dict[str, object]:
        return board_memo_status(run_id)

    @skill.tool(
        "continue_run",
        description=(
            "Idempotent resume for a paused board-memo run. "
            "Inputs: run_id*, request_id*, response* "
            "(audience: board|executive|investor, "
            "recommendation: approve|revise|defer), optional caller_id. "
            "Seals PDF artifact + composite Envelope; duplicate calls replay."
        ),
    )
    def continue_run(
        run_id: str,
        request_id: str,
        response: dict[str, object],
        caller_id: str = "anonymous",
    ) -> dict[str, object]:
        return continue_board_memo(
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
        description="Cancel a paused board-memo run (terminal cancelled disposition).",
    )
    def cancel(run_id: str, caller_id: str = "anonymous") -> dict[str, object]:
        return cancel_run(run_id, caller_id=caller_id)

    return skill
