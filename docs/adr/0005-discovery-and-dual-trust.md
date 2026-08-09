# ADR 0005: Discovery, dual trust, thin harness

- **Status:** Accepted
- **Date:** 2026-08-09
- **Issues:** [#62](https://github.com/lbliii/orrery/issues/62), strategy saga [#56](https://github.com/lbliii/orrery/issues/56), product saga [#1](https://github.com/lbliii/orrery/issues/1)
- **Parent epic:** [#57](https://github.com/lbliii/orrery/issues/57) Strategy freeze
- **Depends on:** [0001](./0001-control-plane-wallet.md), [0004](./0004-publisher-direct-call.md)
- **Plan:** [vending-machine-sky.md](../plan/vending-machine-sky.md)

## Context

Harnesses and skill hosts are under pressure to **bundle everything** —
catalogs, semantic routers, tool execution, memory, commerce. That produces
fat agents, wrong-route tax, and centralized compute.

Orrery’s shape is the opposite: a **vending machine for live expertise** on
[orrery.lol](https://orrery.lol). Agents stay thin; publishers stay specialists;
Orrery stays Skill DNS + wallet + trust labels. Gaze shelves SKUs; resolve
locks the row; call goes publisher-direct (ADR 0004); verify seals the receipt.

Evidence from local DORI (~5d): implement-route accept ~36%, catalog
collisions, empty verification tables — the failure mode of a product-level
“pick the skill” router. Saga #1 and ADR 0001 already freeze control vs data
plane; this ADR freezes discovery and demand-side trust so we do not rebuild
that router or soft-proxy everyone’s tools.

## Decisions

### 1. Agent is the semantic router; Orrery is shelf + DNS

| Role | Owner | Responsibility |
| --- | --- | --- |
| **Shelf / gaze** | Orrery | Bounded shortlist: names, blurbs, prices, facets, trust pills — no valuable tool body |
| **DNS / resolve** | Orrery | Exact lock: endpoint, digest, key, price, alg |
| **Semantic pick** | **Agent / harness** | Ranks (or ignores) the shortlist; may re-query with tighter facets |
| **Execute** | Publisher | Live MCP tools; reactive body at call time |
| **Verify / meter** | Orrery | Envelope verify, wallet, trust aggregates |

Once a name is chosen, resolve is exact — no fuzzy second guess. Gaze never
returns the live body an offline clone would need.

### 2. Namespaces + facets as scale levers; optional RAG is retrieval-only

At million-star scale, discovery is layered — not a global embedding soup:

| Layer | Owner | Role |
| --- | --- | --- |
| **Namespace** | Orrery | Primary taxonomy / tenancy (`public/*`, `acme/*`) |
| **Facets** | Orrery | Filters: kind, price band, reactive/live, oracle_ok, satisfaction, publisher |
| **Gaze index** | Orrery | Cheap progressive disclosure (bounded shortlist, e.g. ≤20) |
| **Optional RAG** | Orrery *or* agent | Retrieval over a **scoped** index — returns **candidates only**, never “the answer” |
| **Semantic pick** | Agent | Final ranking among candidates |
| **Resolve** | Orrery | Exact lock |

Embeddings (if any) are a retrieval aid inside a namespace/facet scope. They
must not become a product API that returns a single forced winner.

### 3. Dual trust: publish oracle × digest-keyed satisfaction × price

| Signal | Side | Keyed by | Shown on |
| --- | --- | --- | --- |
| Publish oracle | Supply | skill / digest | Resolve row, star page, gaze pill |
| Call outcomes | Demand (auto) | digest + envelope_id | Aggregates: sealed %, break % |
| Agent rating | Demand (explicit) | digest + envelope_id (or failed call id) | Compact pill + optional one-liner |
| Price | Commerce | resolve record | Gaze + resolve |

- Supply trust stays `check · freeze · smoke` (existing publish oracle).
- Demand trust is **digest-keyed**: ratings decay or reset when digest changes.
- Rating vocabulary (v1): `useful | stale | broken | wrong-price` (+ optional
  short note). No star essays; no “did you accept the route?” ceremony.
- Money and satisfaction evidence attach to Envelope identity (or an explicit
  forge/break report tied to a call attempt). Satisfaction is not a payment
  signal — wallet rules stay in ADR 0001–0003.

### 4. Thin harness / distributed load

Harnesses own UX and judgment. Publishers own expertise and live compute.
Orrery owns name, meter, and trust labels. Services are **not** bundled into
every agent.

Complement, don’t replace, DORI-like process hosts: those answer *how to
work*; Orrery answers *what to invoke and prove*. Requiring a process skill
host to use Orrery is out of scope.

Vending-machine loop: **Gaze → Resolve → Call → Verify** (+ optional `rate`).
No workshop ceremony on the hot path.

### 5. Explicit Not now

- **Embedding winner-picker** — Orrery as global embedding router that selects
  one star (DORI failure mode)
- **Yelp free-text reviews** — free-text review marketplace / social feed /
  star essays
- **Proxy-all-calls** — reverse-proxy or host everyone’s tool execution
  (reaffirms ADR 0001 / 0004); Orrery-as-FaaS / scale-to-zero compute host
- Stripe charges per tool call (ADR 0001 / 0003)
- Requiring DORI (or any process skill host) to use Orrery
- Constellation authoring editor (viewer + run first)

## Consequences

- Implementers cite this ADR + [vending-machine-sky](../plan/vending-machine-sky.md)
  for discovery/trust disputes; saga #1 north-star language should name the
  vending-machine + thin-harness loop (#63).
- Gaze work (caps, facets, oracle pills) stays index-shaped; satisfaction
  schema and `rate` land under epic #9 without inventing a review product.
- Optional scoped RAG stays feature-flagged and candidate-only (#61 / #72).
- Product resolve records continue to advertise publisher-shaped endpoints
  (`mcp://orrery.lol/s/…`); dogfood `/mcp` on this host remains demo-only.

## Links

- ADR ticket: https://github.com/lbliii/orrery/issues/62
- Strategy saga: https://github.com/lbliii/orrery/issues/56
- Product saga: https://github.com/lbliii/orrery/issues/1
- Strategy plan: [vending-machine-sky.md](../plan/vending-machine-sky.md)
- Control plane: [0001-control-plane-wallet.md](./0001-control-plane-wallet.md)
- Publisher-direct call: [0004-publisher-direct-call.md](./0004-publisher-direct-call.md)
