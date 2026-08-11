"""Publish-oracle examples for the place-hours Star."""

from __future__ import annotations

from chirp.skill.smoke import CorpusPrompt

CORPUS: tuple[CorpusPrompt, ...] = (
    CorpusPrompt(
        id="place-hours-nyc-smoke",
        prompt="Is Central Park Cafe open now?",
        tool="answer",
        arguments={"venue": "central-park-cafe-nyc"},
        required_facts=("Central Park Cafe", "open_now", "hours", "offline", "answer"),
    ),
    CorpusPrompt(
        id="place-hours-london-smoke",
        prompt="What are the hours for the British Museum Cafe fixture?",
        tool="place_hours",
        arguments={"venue": "british-museum-london"},
        required_facts=("British Museum Cafe", "hours", "timezone", "orrery-fixtures"),
    ),
)
