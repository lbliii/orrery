# Plan: Vending-machine sky (discovery, trust, thin harnesses)

- **Status:** Draft (strategy freeze) — saga [#56](https://github.com/lbliii/orrery/issues/56); ADR [#62](https://github.com/lbliii/orrery/issues/62) Accepted
- **Date:** 2026-08-09
- **Parent product saga:** [#1](https://github.com/lbliii/orrery/issues/1)
- **Strategy saga:** [#56](https://github.com/lbliii/orrery/issues/56)
- **Depends on:** [ADR 0001](../adr/0001-control-plane-wallet.md), [ADR 0004](../adr/0004-publisher-direct-call.md)
- **Accepted ADR:** [0005-discovery-and-dual-trust.md](../adr/0005-discovery-and-dual-trust.md) ([#62](https://github.com/lbliii/orrery/issues/62))
- **Feeds:** Epics [#7](https://github.com/lbliii/orrery/issues/7) Namespaces, [#9](https://github.com/lbliii/orrery/issues/9) Trust & Commerce

## GitHub issue map

| Sprint | Epic | Tasks |
| --- | --- | --- |
| S0 | [#57](https://github.com/lbliii/orrery/issues/57) Strategy freeze | [#62](https://github.com/lbliii/orrery/issues/62) ADR 0005 · [#63](https://github.com/lbliii/orrery/issues/63) Update #1 |
| S1 | [#58](https://github.com/lbliii/orrery/issues/58) Gaze as shelf | [#64](https://github.com/lbliii/orrery/issues/64) Cap · [#65](https://github.com/lbliii/orrery/issues/65) Facets · [#66](https://github.com/lbliii/orrery/issues/66) Oracle on gaze |
| S2 | [#59](https://github.com/lbliii/orrery/issues/59) Satisfaction | [#67](https://github.com/lbliii/orrery/issues/67) Schema · [#68](https://github.com/lbliii/orrery/issues/68) `rate` · [#69](https://github.com/lbliii/orrery/issues/69) Pills |
| S3 | [#60](https://github.com/lbliii/orrery/issues/60) Namespace gaze | [#70](https://github.com/lbliii/orrery/issues/70) Scoped match · [#71](https://github.com/lbliii/orrery/issues/71) Cross-ns docs |
| S4 | [#61](https://github.com/lbliii/orrery/issues/61) Scoped RAG | [#72](https://github.com/lbliii/orrery/issues/72) Feature-flagged retrieval |

## Why this matters

Harnesses and skill hosts are under pressure to **bundle everything** — catalogs, semantic routers, tool execution, memory, commerce. That produces fat agents, wrong-route tax, and centralized compute. Orrery’s shape is the opposite: a **vending machine for live expertise**. Agents stay thin; publishers stay specialists; Orrery stays DNS + wallet + trust labels.

Consequences if we miss this:

1. We rebuild DORI-style semantic routing (“we pick the skill”) and inherit ~36% accept rates and catalog collisions.
2. We soft-proxy everyone’s tools and re-centralize the bundle (violates ADR 0004).
3. At a million stars, gaze dumps libraries into context and agents drown.
4. Trust stays supply-only (publish oracle) with no demand-side satisfaction keyed to digests.
5. Harnesses keep frantically reinventing capability hosting instead of pointing.

**Fix:** Freeze the vending-machine loop, treat the agent as the semantic router, scale discovery via namespaces + facets (not embeddings-as-decision), and add digest-keyed caller ratings beside the publish oracle — while keeping compute at publishers.

## Evidence

| Source | Key finding | Proposal impact |
| --- | --- | --- |
| Local DORI (~5d) | `implement` route accept ~36%; winner scores mostly 0.5–0.9 | FIXES — no product-level “pick the skill” router |
| Local DORI | 88 abandoned / 61 completed; ~70 auto-abandon 24h | FIXES — no begin/complete lifecycle on the call path |
| Local DORI | `verification_events` / compliance tables empty | FIXES — Envelope verify is the receipt, not optional telemetry |
| Local DORI | Orrery asks misrouted (`astra-gitops`, `nvcf-ngc-cli`, …) | FIXES — exact resolve; gaze returns shortlist only |
| Saga #1 / ADR 0001 | Control plane ≠ data plane; reactive stars | FIXES — keep distribution; live truth at publisher |
| ADR 0004 | Agent → publisher MCP; aggregate `/mcp` is dogfood | FIXES — thin harness, no proxy-all |
| `catalog/gaze.py` | Progressive disclosure: names/blurbs/prices only | MITIGATES — extend with facets + trust pills, keep payload-free |
| `trust/oracle.py` | Supply-side `check · freeze · smoke` only | FIXES — add demand-side satisfaction keyed to digest |
| Product discussion | Vending machine + distributed load vs harness monoliths | FIXES — named principles below |

## Principles (named)

1. **Vending machine** — Gaze → Resolve → Call → Verify. Insert intent, get sealed truth, leave. No workshop ceremony on the hot path.
2. **Agent is the semantic router** — Orrery does not decide the winner among skills. It shelves SKUs; the agent ranks a shortlist.
3. **Thin harness / distributed load** — Harnesses own UX and judgment. Publishers own expertise and live compute. Orrery owns name, meter, and trust labels. Services are not bundled into every agent.
4. **DNS is sacred** — Once a name is chosen, resolve is exact (endpoint, digest, key, price). No fuzzy second guess.
5. **Dual trust** — Supply: publish oracle. Demand: caller satisfaction tied to Envelope/digest. Ratings decay or reset when digest changes.
6. **Complement, don’t replace, DORI** — DORI-like systems answer *how to work*. Orrery answers *what to invoke and prove*.

## Invariants

These must remain true throughout or we stop and reassess:

1. **No valuable payload in gaze** — Gaze/search/describe never return the live body an offline clone would need.
2. **Call is agent → publisher** — Orrery does not reverse-proxy third-party star execution (dogfood stars on this host are demos only).
3. **Money and trust attach to verify** — Debit and satisfaction evidence require Envelope identity (or explicit forge/break report tied to a call attempt).
4. **Gaze returns a bounded shortlist** — Default cap (e.g. ≤20 hits); never “here are 1000 skills.”
5. **Namespaces are tenancy + trust scope** — Not a flat global embedding soup.

## Target architecture

```text
┌─────────────┐     gaze (shortlist + facets + trust pills)
│   Agent /   │ ──────────────────────────────────────────►  Orrery control plane
│   Harness   │     resolve (exact DNS row)
│             │ ──────────────────────────────────────────►  Skill DNS
│             │     call (MCP tools)
│             │ ──────────────────────────────────────────►  Publisher star
│             │     verify Envelope + optional rate()
│             │ ──────────────────────────────────────────►  Orrery trust/wallet
└─────────────┘

Optional local process skills (DORI-like) stay on the harness — out of band.
```

### Discovery at million-star scale

| Layer | Owner | Role |
| --- | --- | --- |
| **Namespace** | Orrery | Primary taxonomy / tenancy (`public/*`, `acme/*`) |
| **Facets** | Orrery | Filters: kind, price band, reactive/live, oracle_ok, satisfaction, publisher |
| **Gaze index** | Orrery | Cheap progressive disclosure (name, blurb, price, digests, pills) |
| **Optional RAG** | Orrery *or* agent | Retrieval over a **scoped** index — never “the answer”; returns candidates |
| **Semantic pick** | **Agent** | Ranks shortlist; may ignore Orrery’s rank order |
| **Resolve** | Orrery | Exact lock |

**Not now:** Orrery as global embedding router that picks one skill (DORI failure mode).

### Trust surfaces

| Signal | Side | Keyed by | Shown on |
| --- | --- | --- | --- |
| Publish oracle | Supply | skill / digest | Resolve row, star page, gaze pill |
| Call outcomes | Demand (auto) | digest + envelope_id | Aggregates: sealed %, break % |
| Agent rating | Demand (explicit) | digest + envelope_id (or failed call id) | Compact pill + optional one-liner |
| Price | Commerce | resolve record | Gaze + resolve |

Rating vocabulary (v1): `useful | stale | broken | wrong-price` (+ optional short note). No star essays, no “did you accept the route?” ceremony.

## Sprint overview

| Sprint | Focus | Effort | Risk | Ships independently? |
| --- | --- | --- | --- | --- |
| **0** | Design freeze: ADR + issue map | 4–6h | Low | Yes (docs only) |
| **1** | Gaze facets + shortlist caps + trust pills (oracle only) | 8–12h | Low | Yes |
| **2** | Satisfaction schema + MCP `rate` + aggregates | 12–16h | Medium | Yes (stub ledger OK) |
| **3** | Namespace-scoped gaze (public vs `acme/*`) | 10–14h | Medium | Yes (ties epic #7 design) |
| **4** | Optional scoped retrieval (namespaced RAG) | 12–20h | Medium | Yes (feature-flagged) |
| **5** | Publisher economics hooks using dual trust | later | High | After Wave 2 wallet |

Wave alignment: Sprint 0–2 sit beside **Wave 0/1** product work and **Wave 2** trust epic. Sprint 3 tracks **Wave 3**. Sprint 4 is optional scale insurance. Do not block Wave 0 pointing loop on ratings.

---

## Sprint 0: Design freeze

**Goal:** Lock decisions so implementers don’t rebuild a skill router or Yelp.

### Task 0.1 — ADR: discovery & dual trust

Landed: [ADR 0005](../adr/0005-discovery-and-dual-trust.md) ([#62](https://github.com/lbliii/orrery/issues/62)) covering:

- Agent is semantic router; Orrery is shelf + DNS
- Facets + namespaces; optional RAG is retrieval-only
- Dual trust (oracle × satisfaction × price)
- Thin harness / distributed load principle
- Explicit Not now (global embedding winner, free-text review marketplace, proxy-all)

**Acceptance:** ADR Accepted; linked from README strategy table and this plan.

### Task 0.2 — File GitHub issues under epics

| Issue (proposed) | Parent | Notes |
| --- | --- | --- |
| Gaze shortlist caps + facets on hits | Gaze / #1 | kind, reactive, price band, oracle_ok |
| Digest-keyed satisfaction + `rate` tool | #9 | Envelope-linked; aggregate pills |
| Namespace-scoped gaze defaults | #7 | `public` vs tenant sky |
| (Later) Scoped retrieval / RAG over gaze index | #1 or #7 | Feature flag; not default route |

**Acceptance:** Issues filed with exit criteria; no implementation required in Sprint 0.

### Task 0.3 — Update saga #1 north-star language

Add one paragraph: vending machine + thin harness / distributed load; DORI complements process, Orrery distributes capability.

**Acceptance:** Saga body updated (or comment with pointer to this plan + ADR 0005).

---

## Sprint 1: Gaze as shelf labels

**Goal:** Make gaze unmistakably an index, not a brain.

### Task 1.1 — Hard shortlist cap

Default `gaze_match` / `gaze_search` max results (e.g. 20); document that agents may re-rank.

**Files:** `catalog/gaze.py`, gaze MCP tools, `/gaze` UI, tests  
**Acceptance:** `uv run pytest` green; API never returns >cap without explicit `limit`; gaze payloads still lack tool bodies (`rg` / tests assert keys).

### Task 1.2 — Facet fields on hits

Add structured facets on `GazeHit` / resolve-derived hits: `kind`, `reactive` (bool), `price_band` or raw price, `oracle_ok`, namespace prefix.

**Acceptance:** MCP JSON and `/api/gaze/*` expose facets; UI can filter without new card chrome.

### Task 1.3 — Trust pills (oracle only)

Surface existing publish-oracle status on gaze hits (reuse `trust.oracle`).

**Acceptance:** Gaze hit includes oracle pill parity with resolve/star; deep-link to `/console/{skill}` where applicable.

---

## Sprint 2: Demand-side satisfaction

**Goal:** Callers can leave machine-usable trust proof without review essays.

### Task 2.1 — Schema

Store: `star_name`, `content_digest`, `envelope_id` (or `call_attempt_id`), `verdict`, `note?`, `caller_namespace?`, `created_at`.  
Aggregates: counts by verdict, sealed_ok rate if available from verify path.

**Acceptance:** ADR or issue spells schema; migrations/stub store documented; ratings keyed to digest (name alone insufficient).

### Task 2.2 — MCP `rate` (or `star_rate`)

Post-call optional tool: requires prior Envelope id from this control plane (or documented failed-call token). Verdict enum only.

**Acceptance:** Cannot rate arbitrary names without a call receipt; tests cover reject paths; no debit logic inside `rate`.

### Task 2.3 — Aggregate pills on gaze/resolve/star

Show compact satisfaction next to oracle (e.g. `94% useful · 12/7d`). Digest change → decay or reset policy documented.

**Acceptance:** UI + MCP fields; empty state is quiet (no fake scores).

---

## Sprint 3: Namespaces as taxonomy

**Goal:** Primary scale lever is scope, not smarter global search.

### Task 3.1 — Gaze node = namespace scope

Public sky vs `acme/*` private sky; default tools already sketched (`GAZE_NODE_TOOLS`). Wire match/search to respect active node.

**Acceptance:** Matching inside `acme` cannot leak private star names to public gaze; tests for allowlist boundary (ties #30).

### Task 3.2 — Cross-namespace refs policy

Constellations may reference public stars (ADR 0004); document in gaze describe.

**Acceptance:** Docs + one dogfood constellation example stating the rule.

---

## Sprint 4: Optional scoped retrieval (later)

**Goal:** Insurance for large namespaces — still not a winner-picker.

### Task 4.1 — Embeddings over blurbs/facets within a namespace

Return candidate IDs only; agent still picks; resolve still exact.

**Acceptance:** Feature-flagged; disabled by default in MVP; eval shows recall@k improvement without forcing top-1.

---

## Sprint 5: Economics using dual trust (horizon)

**Goal:** Publisher share / ranking inputs can use oracle × satisfaction × volume — without Orrery executing their stars.

**Acceptance:** Design-only until Wave 2 wallet + Wave 5 payouts; no Stripe-per-call.

---

## Risk register

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Accidental semantic “winner” API | Medium | High | Sprint 0 ADR Not now; gaze returns list not single forced skill |
| Ratings become Yelp / sybil farm | Medium | High | Sprint 2: Envelope-gated rate; digest keying; aggregates only |
| Proxy creep (“just host their MCP”) | Medium | High | Invariant 2; ADR 0004; dogfood labeled demo |
| Facet/RAG complexity blocks Wave 0 | Medium | Medium | Ratings/RAG after pointing loop green; Sprint 4 deferred |
| Namespace leakage | Medium | High | Sprint 3 + issue #30 allowlists |
| Harness still bundles everything | Low | Medium | Positioning in saga + connect page: point, don’t install |

## Success metrics

| Metric | Current | After Sprint 1 | After Sprint 2–3 |
| --- | --- | --- | --- |
| Agent loop steps (happy path) | Gaze/resolve/call/verify exist | Cap + facets documented | + optional rate; still ≤5 tool calls |
| Gaze max hits (default) | Unbounded / soft | ≤20 | ≤20 scoped by namespace |
| Trust signals on SKU | Oracle only | Oracle on gaze | Oracle + satisfaction aggregates |
| Product routing = embedding winner | Temptation | Explicitly forbidden in ADR | Still forbidden |
| Harness needs local skill host for live truth | Dogfood only | Unchanged | Unchanged (publisher-direct) |

## Relationship to existing work

- **Saga #1** — This plan sharpens Waves 0–3 positioning; does not replace the wave table.
- **ADR 0001 / 0002 / 0003** — Wallet and Stripe unchanged; satisfaction is not a payment signal.
- **ADR 0004** — Reinforced: distribution requires publisher-direct calls.
- **ADR 0005** — Accepted freeze of discovery + dual trust + thin harness ([0005](../adr/0005-discovery-and-dual-trust.md)).
- **Epic #9** — Sprint 2 lands under Trust & Commerce Phase A adjacent / Phase B design.
- **Epic #7 / #28 / #29 / #30** — Sprint 3 depends on tenant routing + allowlist decisions.
- **DORI** — Remains process/guidance; Orrery must not absorb its catalog-router role.

## Not now (restate)

- Global embedding router that selects one star
- Free-text review marketplace / social feed
- Proxy-all-calls or Orrery-as-FaaS
- Stripe per tool call
- Requiring DORI (or any process skill host) to use Orrery
- Constellation authoring editor

## Next action

1. Review this plan.  
2. Sprint 0: ADR 0005 Accepted — finish #63 + epic exit on #57.
3. Keep coding Wave 0/1 pointing + reactive stars in parallel — do not wait on Sprint 2–4.
