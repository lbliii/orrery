# Star evaluation — L0–L5 checklist

- **Status:** Draft — epic [#114](https://github.com/lbliii/orrery/issues/114)
- **Date:** 2026-08-09
- **Parent saga:** [#76](https://github.com/lbliii/orrery/issues/76) Specimen sky
- **Plan:** [star-eval.md](../plan/star-eval.md)
- **Related:** [scouting.md](./scouting.md) (litmus for *what* to ship), this page (how to *eval* it)

Short instrument manual for every new **public** star. Copy the acceptance
block onto the star issue. Layers L2–L5 are documented for horizon work; only
**L0 + L1** gate publish / `oracle_ok` today.

## Layer table

| Layer | What | Gate? | Now status |
| --- | --- | --- | --- |
| **L0** | Contract + allowlist-negative tests | CI (`pytest`) | Required |
| **L1** | Non-empty `corpus.py` (`CORPUS`) + Chirp smoke | Boot publish / `oracle_ok` | Required |
| **L2** | Live canary (scheduled) | Ops only | Not now (#118) |
| **L3** | Envelope verify + satisfaction | Gaze/resolve pills | Implemented (#120) — [eval-health](../operations/eval-health.md) |
| **L4** | Constellation composite smoke | Constellation publish | Not now (#119) |
| **L5** | Optional agent-loop / `evals.json` | Demo / interop | Not now (#121) |

**LLM rubric is Not now for the publish gate.** Prefer deterministic
assertions on Envelope facts. Agent Skills `evals.json` is L5 interop only —
never a substitute for L1 `CorpusPrompt` smoke.

## Litmus (eval-shaped)

Before calling a star eval-ready:

1. Out-of-allowlist input fails loud (error key / exception)?
2. Happy-path payload keys / types match `contract.py`?
3. `stars/<pkg>/corpus.py` exports non-empty `CORPUS: tuple[CorpusPrompt, …]`?
4. `star.toml` `[publish].corpus` points at that attribute?
5. Fixtures cover L0–L1 offline (no live upstream required for CI)?

## L0 pattern (pytest)

Reusable helpers live in [`tests/stars/helpers.py`](../../tests/stars/helpers.py).

Apply to every allowlisted / egress-bound star:

1. **Allowlist negative** — call with a non-admitted SKU/URL/host; assert a
   loud fail (`error` key or typed exception). Pure-transform stars (empty
   `allowed_egress`) assert contract types instead.
2. **Contract hold** — `tool_schemas()` keys match the manifest tools; required
   payload fields are present on the happy path.
3. **Egress cover** — when `policy.allowed_egress` is non-empty, the contract’s
   canonical upstream URL origin is covered by that allowlist.

Dogfood examples: `tests/stars/test_l0_patterns.py` (world-time, source-watch,
html-to-pdf).

## L1 convention (corpus)

Every public star package ships:

```text
stars/<pkg>/
  star.toml          # [publish] corpus = "stars.<pkg>.corpus:CORPUS"
  corpus.py          # CORPUS: tuple[CorpusPrompt, ...]  with ≥1 entry
  contract.py
  service.py
  skill.py
```

Rules:

- Missing module, bad import ref, or empty `CORPUS` ⇒ **not** `oracle_ok` and
  boot publish validation fails (unless `ORRERY_SKIP_PUBLISH=1`).
- Prompts use the star’s **canonical** tool names (direct MCP), required fact
  substrings that appear in the sealed payload, and fixture-friendly args.
- Host aggregate smoke (`dogfood.DOGFOOD_CORPUS`) may add gaze/resolve/launch-gate
  prompts; it does not replace the per-star `CORPUS`.

Loader: [`stars/_core/corpus.py`](../../stars/_core/corpus.py).

## L4 implemented smoke: stale-proof

`orrery/stale-proof` has deterministic component-success and component-failure
tests. Its direct `run` envelope contains the complete World Time and Source
Watch evidence, and produces `fresh_proof` only when both are present;
otherwise it is explicitly `incomplete`. This is a bounded composition smoke,
not a claim that Orrery deployed anything or persisted an agent baseline.

## Copy-paste acceptance (every new public star)

```markdown
### Star eval (required — epic #114)

- [ ] **L0** Allowlist-negative (or contract-type) test using `tests/stars/helpers.py`
- [ ] **L0** Contract schemas + happy-path payload keys hold
- [ ] **L1** `corpus.py` with ≥1 `CorpusPrompt`; `star.toml` `[publish].corpus` set
- [ ] **Not now:** LLM rubric is not the publish gate
- [ ] L2 canary / L3 satisfaction / L4 constellation / L5 evals.json — out of scope unless that epic says otherwise
```

## Relationship

- **Plan** — full L0–L5 roadmap: [star-eval.md](../plan/star-eval.md)
- **#76** — specimen stars inherit this checklist
- **#9 / #34** — oracle pills stay L1-backed
- **#59 / #67 / #69** — L3 demand-side: [satisfaction schema](../design/satisfaction-schema.md),
  ``rate`` store, aggregate pills; L3 composite: [eval-health](../operations/eval-health.md) (#120)
- **Scouting** — whether a SKU belongs in the sky: [scouting.md](./scouting.md)
