"""Publish-oracle examples for the flight-status Star."""

from __future__ import annotations

from chirp.skill.smoke import CorpusPrompt

CORPUS: tuple[CorpusPrompt, ...] = (
    CorpusPrompt(
        id="flight-status-aa100-smoke",
        prompt="What is the status of flight AA100 on 2026-08-11?",
        tool="answer",
        arguments={"flight": "AA100", "date": "2026-08-11"},
        required_facts=("on_time", "JFK", "LAX", "offline", "answer"),
    ),
    CorpusPrompt(
        id="flight-status-delay-smoke",
        prompt="Check allowlisted flight UA456 status offline.",
        tool="status",
        arguments={"flight": "UA456", "date": "2026-08-11"},
        required_facts=("landed", "SFO", "ORD", "orrery-fixtures"),
    ),
)
