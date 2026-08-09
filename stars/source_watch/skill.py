"""Chirp/MCP adapter for the Source Watch contract.

No source-observation logic belongs here: this module only translates the
canonical contract into a signed Chirp skill with its natural tool names.
"""

from __future__ import annotations

from typing import Any

from chirp.skill import Skill

from stars.signing import public_star_signing_key

from .contract import ANSWER_MAX_CHARS, DEFAULT_SOURCE, STAR_VERSION
from .service import answer as answer_from_source
from .service import diff as diff_from_source
from .service import observe as observe_from_source


def build_skill(
    *,
    private_key: Any | None = None,
    answer_tool_name: str = "answer",
) -> Skill:
    """Build a Source Watch skill, optionally aliasing ``answer`` for an aggregate host."""
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_SOURCE_WATCH_PRIVATE_KEY",
        key_id_env="ORRERY_SOURCE_WATCH_KEY_ID",
        default_key_id="orrery-source-watch-1",
    )
    skill = Skill(
        "source-watch",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool("observe", description="Fetch an allowlisted source and record digest evidence")
    def observe(source: str = DEFAULT_SOURCE) -> dict[str, object]:
        return observe_from_source(source)

    @skill.tool("diff", description="Fetch now and compare normalized content to a known digest")
    def diff(source: str = DEFAULT_SOURCE, since_digest: str = "") -> dict[str, object]:
        return diff_from_source(source, since_digest)

    @skill.tool(
        answer_tool_name,
        description="Answer from a freshly fetched official source with bounded evidence",
    )
    def answer(
        question: str,
        source: str = DEFAULT_SOURCE,
        max_chars: int = ANSWER_MAX_CHARS,
    ) -> dict[str, object]:
        return answer_from_source(question, source, max_chars)

    return skill
