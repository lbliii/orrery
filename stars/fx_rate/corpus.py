"""Publish-oracle examples for the FX rate Star."""

from __future__ import annotations

from chirp.skill.smoke import CorpusPrompt

CORPUS: tuple[CorpusPrompt, ...] = (
    CorpusPrompt(
        id="fx-rate-usd-eur-smoke",
        prompt="What was the USD/EUR rate on 2026-06-01?",
        tool="answer",
        arguments={"pair": "usd-eur", "as_of": "2026-06-01"},
        required_facts=("USD", "EUR", "0.8812", "2026-06-01", "offline", "answer"),
    ),
    CorpusPrompt(
        id="fx-rate-usd-jpy-smoke",
        prompt="Look up the allowlisted USD/JPY fixture for 2026-08-01.",
        tool="fx_rate",
        arguments={"pair": "usd-jpy", "as_of": "2026-08-01"},
        required_facts=("USD", "JPY", "147.35", "orrery-fixtures", "offline"),
    ),
)
