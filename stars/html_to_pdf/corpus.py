"""Publish-oracle examples for the html-to-pdf Star."""

from __future__ import annotations

from chirp.skill.smoke import CorpusPrompt

SMOKE_HTML = "<!doctype html><html><body><h1>Orrery</h1></body></html>"

CORPUS: tuple[CorpusPrompt, ...] = (
    CorpusPrompt(
        id="html-to-pdf-convert-smoke",
        prompt="Convert a short HTML document to PDF.",
        tool="convert",
        arguments={"html": SMOKE_HTML},
        required_facts=("application/pdf", "page_count", "byte_length", "artifact_url", "sha256"),
    ),
)
