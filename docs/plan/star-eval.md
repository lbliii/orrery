# Plan: Star evaluation (L0–L5)

- **Status:** Draft — **epic [#114](https://github.com/lbliii/orrery/issues/114)** under [#76](https://github.com/lbliii/orrery/issues/76) / [#9](https://github.com/lbliii/orrery/issues/9)
- **Date:** 2026-08-09
- **Depends on:** Chirp `chirp.skill.smoke` (CorpusPrompt + faithful-answer scorer), publish oracle, [#59](https://github.com/lbliii/orrery/issues/59) demand-side satisfaction
- **Design checklist:** [star-eval.md](../design/star-eval.md)

## GitHub issue map

| Layer | Task |
| --- | --- |
| Spec | [#115](https://github.com/lbliii/orrery/issues/115) Design checklist |
| L0 | [#116](https://github.com/lbliii/orrery/issues/116) Allowlist-negative patterns |
| L1 | [#117](https://github.com/lbliii/orrery/issues/117) Require CORPUS for oracle_ok |
| L2 | [#118](https://github.com/lbliii/orrery/issues/118) world-time canary |
| L4 | [#119](https://github.com/lbliii/orrery/issues/119) Constellation smoke |
| L3 | [#120](https://github.com/lbliii/orrery/issues/120) Verify + satisfaction health |
| L5 | [#121](https://github.com/lbliii/orrery/issues/121) Optional evals.json / agent-loop |

## Why this matters

Specimen stars (#76) without a clear eval bar will either (a) ship untrustworthy SKUs, or (b) accidentally adopt Agent Skills–style **LLM rubrics on transcripts** as the publish gate — which grades harness chatter, not vending-machine truth.

Consequences:

1. Oracle pills lie (`oracle_ok` without real faithfulness).
2. Live upstream rot goes unnoticed until users burn tokens browsing again.
3. Constellations compose flaky nodes into flaky gates.
4. Interop with `evals.json` gets confused with *definition* of quality.

**Fix:** Define star eval as **layered, mostly deterministic** checks. Reuse Chirp smoke as L1. Treat Agent Skills `evals.json` as optional L5 interop only.

## Evidence

| Source | Finding | Impact |
| --- | --- | --- |
| `chirp.skill.smoke` | Golden NL → tool → faithful-to-engine-JSON; refusals/catalogs fail | FIXES — L1 already exists |
| Orrery `stars/*/corpus.py` | Per-star CorpusPrompt wired into publish gate | MITIGATES — formalize as required for every specimen star |
| Agent Skills `evals/evals.json` | prompt + expectations, often LLM-graded transcript | UNRELATED as publish gate; optional L5 export |
| Dual trust (#59) | Demand-side ratings keyed to digest | FIXES — L3 |
| DORI telemetry lesson | Empty verification tables = unused optional governance | FIXES — L0–L2 must be CI/boot gates, not optional |

## Invariants

1. **Publish gate is not an LLM rubric.** L0–L1 (and constellation L4 smoke) stay deterministic / fixture-backed where possible.
2. **Grade Envelope + facts**, not essay quality.
3. **Allowlist negatives are first-class** — out-of-allowlist must fail loud in tests.
4. **L2 live canary ≠ PR blocker by default** — scheduled/opt-in; L0–L1 block merge/boot.
5. **Every specimen star ships L0+L1** before gaze lists it as oracle-ok.

## Target architecture (layers)

```text
L0 Contract     schema, types, allowlist reject          → pytest / CI
L1 Smoke        CorpusPrompt + faithful scorer           → publish oracle (boot)
L2 Canary       live upstream call on schedule           → ops alert / console
L3 Demand       Envelope verify + satisfaction (#59)     → gaze/resolve pills
L4 Constellation composite graph smoke                   → constellation publish
L5 Agent loop   optional gaze→resolve→call harness       → demo / evals.json export
```

| Layer | Artifact | Pass means |
| --- | --- | --- |
| L0 | `tests/stars/…`, contract tests | Bad SKU / bad URL fails; happy path types hold |
| L1 | `stars/<name>/corpus.py` | Faithful to payload; no refusal/catalog/skip |
| L2 | canary job / script | Live call returns sealable payload; digest policy documented |
| L3 | rate + aggregates | Callers can attest; quiet empty state OK |
| L4 | constellation corpus | Composite Envelope; node failures surface |
| L5 | optional `evals/` | Agent finds SKU and calls; token/time note vs browse |

### Agent Skills `evals.json` (L5 only)

- **May** export or mirror thin cases: prompt → expect resolve name / tool / required fact substrings.
- **Must not** replace L1 publish smoke.
- Prefer deterministic assertions (contains digest field, tool name, fact keys) over LLM rubrics when possible.

## Litmus for “good star eval”

1. Digest mismatch or missing canonical URL fails?
2. Allowlist miss fails?
3. Refusal / tool catalog fails L1?
4. L0–L1 runnable offline with fixtures?
5. L2 clearly labeled live/canary?

## Sprint overview

| Sprint | Focus | Effort | Risk | Ships independently? |
| --- | --- | --- | --- | --- |
| **0** | Design note + checklist for specimen stars | 3–4h | Low | Yes |
| **1** | L0 template + enforce L1 corpus on existing stars | 6–10h | Low | Yes |
| **2** | L2 canary harness (one star first: world-time) | 8–12h | Medium | Yes |
| **3** | L4 constellation smoke pattern (`stale-proof`) | 6–10h | Medium | Yes |
| **4** | L3 wire-up with satisfaction epic #59 | 4–8h | Medium | Yes (depends #59) |
| **5** | Optional L5 / evals.json export for parable | 6–10h | Low | Yes |

## Sprint 0 — Spec

Document layers in this plan + short `docs/design/star-eval.md`. Add “eval checklist” to specimen sky star acceptance (#76).

**Acceptance:** Checklist quoted on #76 and epic; README link.

## Sprint 1 — L0 + L1 bar

- Shared pytest patterns for allowlist negatives
- Require non-empty `CORPUS` per public star package
- CI/boot: missing corpus ⇒ not oracle_ok

**Acceptance:** `uv run pytest` covers L0 negatives for html-to-pdf / world-time / source-watch; corpus required in star package docs.

## Sprint 2 — L2 canary

- Script or scheduled job: call live star, verify Envelope, record as-of
- Start with `orrery/world-time`; document flake policy

**Acceptance:** One documented canary path; does not fail every PR by default.

## Sprint 3 — L4 constellation smoke

- Pattern for composite corpus on story constellations
- Prototype on `stale-proof` when #88 lands

**Acceptance:** Constellation smoke doc + at least one implemented graph test.

## Sprint 4 — L3 demand

- Tie verify success/fail (+ optional rate) into eval dashboards / pills
- Depends on #67–#69 (closed/merged: satisfaction schema, ``rate`` store, aggregate pills)

**Shipped (#120):** Gaze ``trust.eval_health`` composes publish-oracle supply
status with digest-matched satisfaction aggregates from
[satisfaction schema](../design/satisfaction-schema.md) (#67) and
[satisfaction pills](../operations/satisfaction-pills.md) (#69). Quiet when
demand is empty or digest-mismatched — no fake scores. Oracle and satisfaction
pills unchanged.

**Acceptance:** Design links satisfaction aggregates to “eval health”; no fake scores.

## Sprint 5 — L5 optional interop

- Thin agent-loop eval for parable (gaze intent → resolve → call)
- Optional `evals/evals.json` export for Agent Skills tooling

**Acceptance:** Documented as non-gating; deterministic checks preferred.

## Risk register

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| LLM rubric becomes publish gate | Medium | High | Invariant 1; Sprint 0 Not now |
| Live canary flakes block deploys | High | Medium | L2 non-blocking default |
| Eval paperwork blocks specimen stars | Medium | Medium | Checklist is L0+L1 only for merge |
| Confusion with process-skill evals | Medium | Low | Naming: “star eval” vs “agent skill evals” |

## Success metrics

| Metric | After Sprint 1 | After Sprint 3 |
| --- | --- | --- |
| Public stars with L1 corpus | 3 dogfood | All specimen stars as they land |
| Allowlist negative tests | ≥1 per allowlisted star | Same |
| Constellation L4 pattern | 0 | ≥1 (`stale-proof`) |
| Publish gate uses LLM rubric | No | Still no |

## Relationship to existing work

- **#76** — Every specimen star task inherits L0+L1 acceptance.
- **#9 / #34** — Oracle pills remain L1-backed.
- **#59 / #67 / #69** — L3 demand-side: [satisfaction schema](../design/satisfaction-schema.md),
  ``rate`` store, aggregate pills; L3 composite: [eval-health](../operations/eval-health.md) (#120)
- **#56** — Dual trust / no ceremony tax: eval must stay hot-path cheap.
- **Chirp smoke** — Do not fork; extend usage and docs.

## Not now

- LLM-as-judge on publish
- Full Agent Skills eval harness as required CI
- Evaluating local filesystem “hands” as public stars
- Blocking merges on flaky live upstream
