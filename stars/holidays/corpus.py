"""Publish-oracle examples for the public holidays Star."""

from __future__ import annotations

from chirp.skill.smoke import CorpusPrompt

CORPUS: tuple[CorpusPrompt, ...] = (
    CorpusPrompt(
        id="holidays-us-2026-smoke",
        prompt="List US public holidays for 2026.",
        tool="answer",
        arguments={"region": "US", "year": 2026},
        required_facts=("US", "2026", "holidays", "offline", "answer"),
    ),
    CorpusPrompt(
        id="holidays-gb-list-smoke",
        prompt="What are the UK bank holidays in 2026?",
        tool="list",
        arguments={"region": "GB", "year": 2026},
        required_facts=("GB", "2026", "holidays", "Christmas Day", "offline"),
    ),
)
