"""Publish-oracle examples for the timezone resolution Star."""

from __future__ import annotations

from chirp.skill.smoke import CorpusPrompt

CORPUS: tuple[CorpusPrompt, ...] = (
    CorpusPrompt(
        id="tz-resolve-new-york-smoke",
        prompt="What IANA timezone is New York in?",
        tool="answer",
        arguments={"place": "new-york"},
        required_facts=("America/New_York", "timezone", "offline", "answer"),
    ),
    CorpusPrompt(
        id="tz-resolve-latlon-smoke",
        prompt="Resolve the timezone for Tokyo coordinates offline.",
        tool="resolve",
        arguments={"latitude": 35.6762, "longitude": 139.6503},
        required_facts=("Asia/Tokyo", "timezone", "latlon:offline"),
    ),
)
