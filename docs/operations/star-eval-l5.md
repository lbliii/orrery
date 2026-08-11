# Star eval L5 (optional agent-loop)

L5 is an **optional, non-gating** interop layer for thin gaze→resolve→call
evals and Agent Skills–compatible `evals/evals.json` export. It does **not**
participate in publish / `oracle_ok` — only L0 + L1 gate boot publish today.

## Contract

| Property | L5 | Publish gate (L0–L1) |
| --- | --- | --- |
| Blocks merge / boot | **No** | Yes (L0 CI; L1 corpus) |
| Affects `oracle_ok` | **No** | Yes |
| LLM rubric on transcript | **Discouraged** | **Forbidden** |
| Deterministic assertions | **Preferred** | Required |
| Artifact | `evals/evals.json`, pytest | `corpus.py`, contract tests |

L5 may export or mirror thin cases: natural-language prompt → expect resolve
name / tool / required fact substrings. **Must not** replace L1 `CorpusPrompt`
smoke or become a CI merge gate.

## Parable demo path (cohort A / stale-proof)

Deterministic offline loop exercised by `tests/test_star_eval_l5.py`:

1. **Gaze** — intent ``stale answer detection`` shortlists ``orrery/stale-proof``
   in the public top-3.
2. **Resolve** — ``CATALOG.resolve("orrery/stale-proof")`` returns the
   constellation record.
3. **Call** — fixture-backed ``run()`` returns ``fresh_proof`` with ``utc`` and
   ``source_status`` (no live upstream, no LLM judge).

This mirrors the cohort-A parable: fresh UTC plus official source digest evidence
without claiming deployment or persistence.

## Export fixture

Minimal Agent Skills interop lives at [`evals/evals.json`](../../evals/evals.json)
with notes in [`evals/README.md`](../../evals/README.md). Expectations are
documentary; pytest applies deterministic checks instead of LLM grading.

## Ops

- **Non-blocking:** L5 failures do not block PR merge or boot publish.
- **No egress required** for the offline demo path (injected fetches).
- **Acceptance:** ``uv run pytest tests/test_star_eval_l5.py -q``

## References

- Plan Sprint 5: [star-eval.md](../plan/star-eval.md) (#121)
- Checklist: [star-eval.md](../design/star-eval.md)
- L4 parable smoke: [stale-proof tests](../../tests/stars/test_stale_proof.py)
- Gaze intent fixtures: [gaze-intents.v1.json](../../tests/gaze-intents.v1.json)
