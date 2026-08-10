# Plan: Tree-handling rim — sealed leaves for agent task trees

- **Status:** Draft (product freeze) — saga [#237](https://github.com/lbliii/orrery/issues/237)
- **Date:** 2026-08-10
- **Parent product saga:** [#1](https://github.com/lbliii/orrery/issues/1)
- **Complements:** [vending-machine-sky.md](./vending-machine-sky.md) (ADR 0005),
  [issue-lifecycle.md](./issue-lifecycle.md),
  [specimen-sky.md](./specimen-sky.md)
- **ADR:** [0006-decision-receipt.md](../adr/0006-decision-receipt.md) (DecisionReceipt);
  [0007-constellation-subtree-contract.md](../adr/0007-constellation-subtree-contract.md)
  (`subtree_contract`: stages, pause_policy, composite_receipt_fields, lease_rule)
- **Evidence:** [Cursor — Agent swarms and the new model economics](https://cursor.com/blog/agent-swarm-model-economics)

## Why this matters

Agent swarms decompose work into trees. Planners need short SKUs; workers need
narrow, sealed facts; coordination happens through the environment (receipts,
digests, design docs)—not by stuffing more chat into context.

Orrery already sells the right shape: gaze → resolve → call → seal. The gap is
positioning and a few primitives so harnesses can **hang sealed leaves on their
own trees** without Orrery becoming the swarm harness, VCS, or skill router.

Without this rim:

1. Workers re-fetch or invent truth into context (token burn + drift).
2. Planners dump catalogs instead of locking a leaf capability.
3. Split-brain design has nowhere cheap to record a citeable decision.
4. Constellations look like demos instead of **frozen planner subgraphs**.
5. We accidentally chase Cursor’s merge/reconciler layer (out of scope).

**Fix:** Treat the public sky as a **tree-handling rim**: bounded stars for
worker leaves, decision-bind for planner freezes, constellations as reusable
subtree contracts (ADR 0007), gaze/cards that name leaves without owning routing.

## Product clues → Orrery bets

| Clue (swarm economics) | Orrery bet | Already in flight |
| --- | --- | --- |
| Context efficiency > raw parallelism | Sealed receipts climb the tree; workers don’t re-hold evidence | Envelope verify, portable receipts |
| Specs as prompts; scarce = intent | Gaze shortlist + agent cards + intent fixtures | #217–#226 (mostly closed) |
| Split-brain / contested design | `decision-bind` (+ ADR cite) receipts | **Net new** |
| Workers bad at absorbing merge context | `manifest-*`, `patch-capture`, structure/link/write checks | #222, #223, #224 |
| Stigmergy / Field Guide | Receipts + digests as environment; not a chat log product | Migration composite receipts (#160+) |
| Constellations / policy graphs | Frozen planner subgraph (`subtree_contract` per ADR 0007) | #157, #213–#216, #164 |
| Cheap workers after frontier plan | Price/trust on verify; payload-free gaze; cost hints on cards | ADR 0005; **facet polish** |
| Do not own swarm VCS | Explicit non-goal | ADR 0004 / 0005 |

## Principles (named)

1. **Leaf runtime, not planner** — Orrery seals facts and stage evidence; the
   harness owns task trees and model mix.
2. **Hang, don’t host** — A receipt is something a tree node can keep; Orrery
   does not retain the agent’s plan.
3. **Constellation = frozen planner subgraph** — Composition is a planner
   decision made durable (ADR 0007), not a chatty orchestrator.
4. **Citeable decisions** — When two workers would invent policy, bind it once
   and cite the digest downstream.
5. **Thin harness / distributed load** — Same as ADR 0005; this plan only adds
   rim SKUs and contracts.

**Process vs product:** How *we* burn down the Orrery GitHub backlog lives in
[`AGENTS.md`](../../AGENTS.md) and [issue-lifecycle.md](./issue-lifecycle.md).
That workflow is **not** a public star. Stars/constellations are only for
sealed results any external agent would hang on *its* tree (see the table in
`AGENTS.md`).

## Non-goals

- Agent swarm VCS, merge reconciler, or megafile decomposer
- Product-level “pick the skill” router (ADR 0005)
- Replacing DORI-like process skills
- Storing full agent transcripts as a product surface

## GitHub issue map

| Epic | Focus | Children |
| --- | --- | --- |
| [#238](https://github.com/lbliii/orrery/issues/238) Protocol leaf runtime | Pure/allowlisted primitives workers call mid-tree | [#222](https://github.com/lbliii/orrery/issues/222), [#223](https://github.com/lbliii/orrery/issues/223), [#224](https://github.com/lbliii/orrery/issues/224) |
| [#239](https://github.com/lbliii/orrery/issues/239) Decision-bind receipts | Citeable decision freeze for planners | [#242](https://github.com/lbliii/orrery/issues/242) design · [#244](https://github.com/lbliii/orrery/issues/244) star |
| [#240](https://github.com/lbliii/orrery/issues/240) Frozen planner-graph constellations | Subtree contracts, pause/continue, composite seal | [#243](https://github.com/lbliii/orrery/issues/243) design (closed → ADR 0007) · [#265](https://github.com/lbliii/orrery/issues/265) wire · [#266](https://github.com/lbliii/orrery/issues/266) docs · [#213](https://github.com/lbliii/orrery/issues/213)–[#216](https://github.com/lbliii/orrery/issues/216) · [#157](https://github.com/lbliii/orrery/issues/157) · migration [#164](https://github.com/lbliii/orrery/issues/164) |
| [#241](https://github.com/lbliii/orrery/issues/241) Planner shelf polish | Tree-role / worker-cost hints on cards + gaze | [#246](https://github.com/lbliii/orrery/issues/246) |

Saga: [#237](https://github.com/lbliii/orrery/issues/237).

## Sprint overview

| Sprint | Focus | Depends on | Ships independently? |
| --- | --- | --- | --- |
| **0** | Saga + designs (DecisionReceipt; constellation-as-subtree) | ADR 0005 | Yes (docs) |
| **1** | Protocol stars #222 / #223 (+ boundary adapter #224) | Wave 1 call path | Yes |
| **2** | `decision-bind` star + dogfood cite in one constellation | Sprint 0 design | Yes |
| **3** | Align content + resumable constellation epics to subtree language | ADR 0007 (#243 closed); resume MCP still needs #152 | Yes (sync/content); resume gated |
| **4** | Optional `tree_role` / `worker_cost` facets on agent cards | #217 closed | Yes (P2) |

## Exit criteria (saga)

1. Public docs state the tree-handling rim in one page (this plan + README hook).
2. At least one **decision-bind** receipt verifies standalone and is citable from
   a constellation composite receipt.
3. Protocol leaf stars (#222/#223) are registered with agent cards and L0+L1 eval.
4. At least one constellation is documented as a **frozen planner subgraph**
   (`subtree_contract` per ADR 0007)—not only as a demo story.
5. README / gaze copy never claims Orrery orchestrates swarms or merges code.

## Success signal

A planner agent can lock a decision digest and a worker can attach sealed
protocol/migration evidence to tree nodes—without Orrery holding the plan or
choosing the next skill.
