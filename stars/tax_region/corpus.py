"""Publish-oracle examples for the tax-region Star."""

from __future__ import annotations

from chirp.skill.smoke import CorpusPrompt

CORPUS: tuple[CorpusPrompt, ...] = (
    CorpusPrompt(
        id="tax-region-us-ca-smoke",
        prompt="Validate this US California sales-jurisdiction record shape.",
        tool="validate",
        arguments={
            "profile": "sales-jurisdiction",
            "jurisdiction": {
                "country": "US",
                "region": "CA",
                "jurisdiction_key": "US-CA",
            },
        },
        required_facts=("valid", "profile_digest", "normalized_jurisdiction", "US-CA"),
    ),
    CorpusPrompt(
        id="tax-region-gb-eng-smoke",
        prompt="Check whether this GB England jurisdiction record matches the profile.",
        tool="validate",
        arguments={
            "profile": "sales-jurisdiction",
            "jurisdiction": {
                "country": "GB",
                "region": "EN",
                "jurisdiction_key": "GB-EN",
            },
        },
        required_facts=("valid", "GB", "jurisdiction_key"),
    ),
)
