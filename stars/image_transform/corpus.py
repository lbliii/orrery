"""Publish-oracle examples for the image-transform Star."""

from __future__ import annotations

from chirp.skill.smoke import CorpusPrompt

CORPUS: tuple[CorpusPrompt, ...] = (
    CorpusPrompt(
        id="image-transform-submit-smoke",
        prompt="Queue a safe PNG color fill and return a run id.",
        tool="submit",
        arguments={"color": "#1a1a2e", "idempotency_key": "image-transform-smoke-1"},
        required_facts=("run_id",),
    ),
)
