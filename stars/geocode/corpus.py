"""Publish-oracle examples for the geocode Star."""

from __future__ import annotations

from chirp.skill.smoke import CorpusPrompt

CORPUS: tuple[CorpusPrompt, ...] = (
    CorpusPrompt(
        id="geocode-new-york-smoke",
        prompt="What are the coordinates for New York?",
        tool="answer",
        arguments={"place": "new-york"},
        required_facts=("New York, NY", "latitude", "longitude", "offline", "answer"),
    ),
    CorpusPrompt(
        id="geocode-tokyo-smoke",
        prompt="Geocode the allowlisted Tokyo place token offline.",
        tool="geocode",
        arguments={"place": "tokyo"},
        required_facts=("Tokyo, Japan", "latitude", "longitude", "orrery-fixtures"),
    ),
)
