"""Publish-oracle examples for the CSV report Star."""

from __future__ import annotations

from chirp.skill.smoke import CorpusPrompt

CORPUS: tuple[CorpusPrompt, ...] = (
    CorpusPrompt(
        id="csv-report-submit-smoke",
        prompt="Queue a tiny CSV report and return a run id.",
        tool="submit",
        arguments={
            "rows": [{"sku": "orrery/world-time", "qty": 1}],
            "idempotency_key": "csv-report-smoke-1",
        },
        required_facts=("run_id", "state"),
    ),
    CorpusPrompt(
        id="csv-report-result-smoke",
        prompt="Poll a managed CSV run by run_id from submit.",
        tool="result",
        arguments={"run_id": "run-placeholder"},
        required_facts=("run_id",),
    ),
)
