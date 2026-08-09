"""Publish-oracle examples for the Source Watch Star."""

from __future__ import annotations

from chirp.skill.smoke import CorpusPrompt

CORPUS: tuple[CorpusPrompt, ...] = (
    CorpusPrompt(
        id="source-watch-observe-smoke",
        prompt="Observe the allowlisted Python release notes source.",
        tool="observe",
        arguments={"source": "python-release-notes"},
        required_facts=(
            "python-release-notes",
            "canonical_url",
            "normalized_sha256",
            "live_at_call",
        ),
    ),
    CorpusPrompt(
        id="source-watch-answer-smoke",
        prompt="Answer from the current allowlisted Python release notes.",
        tool="answer",
        arguments={"question": "What security guidance is included?", "max_chars": 120},
        required_facts=("answer", "extractive", "evidence", "normalized_sha256"),
    ),
)
