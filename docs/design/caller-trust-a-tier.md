# Design: Caller-trust A-tier

- **Status:** Accepted (planner freeze)
- **Date:** 2026-08-14
- **Parent saga:** [#1](https://github.com/lbliii/orrery/issues/1)
- **Epic:** [#426](https://github.com/lbliii/orrery/issues/426)
- **Designs:** [#427](https://github.com/lbliii/orrery/issues/427) (errors),
  [#428](https://github.com/lbliii/orrery/issues/428) (vocabulary)
- **Binds:** [ADR 0010](../adr/0010-aggregate-mcp-call-skill.md),
  [ADR 0011](../adr/0011-error-surfaces.md),
  [public-loop-vocabulary.md](./public-loop-vocabulary.md)

## Why this pass exists

The claimable swarm queue is empty. Five adversarial personas (architect,
senior, designer, marketing, product lead) graded the live sky. Product
lead vetoed a lint/refactor swarm. Architect showed ADR 0010 is only
fully honored on `call_skill`. Those are the same product: **a caller
must parse every failure on the advertised loop, and the human pages
must teach the same loop.**

This is not a public Star. Process + contracts live in GitHub and ADRs.

## Six practices (target A / S)

| # | Practice | A / S means |
| --- | --- | --- |
| 1 | Channel discipline | Expected failures return; crashes raise+log; HTTP/MCP only adapt |
| 2 | Stable machine codes | Snake_case; no public `str(exc)` |
| 3 | One wire shape per boundary | Three channels, not one mega-shape |
| 4 | Shared primitives | Identical **policy** is shared; per-star identity is not |
| 5 | Fail loud at publish | Startup corpus raises; call-time is structured |
| 6 | Caller-safe messages | Agents get codes; humans get next action; pages never replace codes |

## Wave 1 (this epic’s first leaves)

1. Promote unsigned MCP `{error}` → ADR 0010 `status:error`.
2. Restore gaze → resolve → call → seal on the homepage.
3. Unify `/mcp` copy with ADR 0010 (not “legacy bridge”).
4. Shared HTTPS egress helper (delete identical `_NoRedirect` copies).
5. Map wallet / namespace page errors to prose + next action.

## Explicitly later (do not fake-ready)

- Dual-trust E2E (gaze → `call_skill` → verify → `rate` + non-quiet pill).
  `rate` is denylisted on default `/mcp`. Needs its own design.
- Canonical JSON merge (`_nfc_wire` vs `_nfc_normalize`) — digest risk.
- MCP private-namespace caller gate (HTTP has it; MCP does not).
- Managed admission structured return; verify `error` codes — wave 2,
  after ADR 0011 is cited by wave-1 MCP leaf.
- Chirp canary #212, RAG #61/#72, GPU #136/#138, new SKUs.

## Sacred (personas agreed)

- “Skills you point at, not install.”
- Gaze → resolve → call → seal.
- Publisher-direct is canonical; `call_skill` is same-origin forwarder.
- Not a skill router, swarm VCS, or MCP directory.
- Envelope verify fields; prepaid wallet when commerce lands.
- Per-star `skill.py` factories stay.
