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
    CorpusPrompt(
        id="html-to-pdf-submit-smoke",
        prompt="Queue a managed PDF run and return a run id.",
        tool="submit",
        arguments={"html": SMOKE_HTML, "idempotency_key": "html-to-pdf-smoke-1"},
        required_facts=("run_id", "state"),
    ),
    CorpusPrompt(
        id="html-to-pdf-result-smoke",
        prompt="Poll a managed PDF run by run_id from submit.",
        tool="result",
        arguments={"run_id": "run-placeholder"},
        required_facts=("run_id",),
    ),
)
