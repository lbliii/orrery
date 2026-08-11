# L5 eval export (optional, non-gating)

This directory holds an Agent Skills–compatible [`evals.json`](./evals.json)
export for the cohort-A **stale-proof** parable path. It is **interop only** —
L5 does not gate publish or `oracle_ok`.

Deterministic checks live in `tests/test_star_eval_l5.py` (gaze shortlist,
resolve name, fixture-backed `run` payload keys). Do not use LLM rubrics on
transcripts as a substitute for L1 `CorpusPrompt` smoke.

See [star-eval-l5](../docs/operations/star-eval-l5.md) for the full contract.
