"""Publish-oracle examples for the World Time Star."""

from __future__ import annotations

from chirp.skill.smoke import CorpusPrompt

CORPUS: tuple[CorpusPrompt, ...] = (
    CorpusPrompt(
        id="world-time-answer-smoke",
        prompt="Answer with the live UTC time.",
        tool="answer",
        arguments={},
        required_facts=("UTC", "live_at_call", "clone_warning", "answer"),
    ),
)
