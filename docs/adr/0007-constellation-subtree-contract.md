# ADR 0007: Constellation-as-subtree contract

- **Status:** Accepted
- **Date:** 2026-08-10
- **Issues:** [#243](https://github.com/lbliii/orrery/issues/243),
  epic [#240](https://github.com/lbliii/orrery/issues/240),
  saga [#237](https://github.com/lbliii/orrery/issues/237)
- **Depends on:** [0005](./0005-discovery-and-dual-trust.md),
  [0006](./0006-decision-receipt.md)
- **Plan:** [tree-handling-rim.md](../plan/tree-handling-rim.md)
- **Aligns with:** [#220](https://github.com/lbliii/orrery/issues/220) (closed)
  run-contract exposure via `gaze_describe` / `explain_policy`

## Context

Constellations are **frozen planner subgraphs**: durable stage graphs with pause
rules and a composite seal—not chatty orchestration demos or an in-Orrery
workflow engine (ADR 0005 thin harness).

Content graphs ([#213](https://github.com/lbliii/orrery/issues/213)–[#216](https://github.com/lbliii/orrery/issues/216)),
resumable decision runs ([#157](https://github.com/lbliii/orrery/issues/157)),
and migration verticals ([#164](https://github.com/lbliii/orrery/issues/164))
share the same vocabulary. Without a normative contract, agents infer stage
names, pause semantics, and composite shape from prose.

Issue [#220](https://github.com/lbliii/orrery/issues/220) already exposes
`run_contract`, `graph_summary`, `dispositions`, and `member_stars` on
constellation agent cards. This ADR adds the **subtree contract** fields that
make a constellation a citeable frozen graph.

## Decision

Adopt **option 2 (subtree contract)** from design [#243](https://github.com/lbliii/orrery/issues/243).
Every public `kind: constellation` agent card MUST publish a `subtree_contract`
object. `gaze_describe` and `explain_policy` MUST return the same object
(alongside existing #220 fields).

### 1. `subtree_contract` (required on constellation cards)

| Top-level field | Required | Meaning |
| --- | --- | --- |
| `stages` | yes | Ordered frozen planner stages (see below) |
| `pause_policy` | yes | When and how durable pause is allowed |
| `composite_receipt_fields` | yes | Terminal composite receipt shape |
| `lease_rule` | yes | Normative lease invariant (see below) |

`subtree_contract` complements `run_contract` (#220): `run_contract` names
entry tool and inputs; `subtree_contract` names the frozen graph and seal.

### 2. `stages[]`

Ordered array of stage objects. Order is the planner freeze; implementers MUST
NOT reorder without a new policy digest.

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | Stable stage id (kebab-case; matches graph node id) |
| `label` | yes | Human/agent-facing stage name |
| `role` | yes | One of `gate`, `witness`, `fan_in`, `composite`, `pause` |
| `star_ref` | no | Resolvable star name when the stage invokes a star |
| `optional` | no | Default `false`; `true` when stage may be skipped by policy |

Example (content-readiness graph):

```json
"stages": [
  {"id": "manifest-bind", "label": "manifest-bind", "role": "gate", "star_ref": "orrery/manifest-bind"},
  {"id": "manifest-preflight", "label": "manifest-preflight", "role": "gate", "star_ref": "orrery/manifest-preflight"},
  {"id": "structure-audit", "label": "structure-audit", "role": "gate", "star_ref": "orrery/structure-audit"},
  {"id": "link-check-bounded", "label": "link-check-bounded", "role": "gate", "star_ref": "orrery/link-check-bounded"},
  {"id": "artifact-seal", "label": "artifact-seal", "role": "composite", "star_ref": "orrery/artifact-seal"}
]
```

### 3. `pause_policy`

| Field | Required | Meaning |
| --- | --- | --- |
| `allowed` | yes | Whether the constellation may enter a durable waiting state |
| `modes` | if `allowed` | Subset of `awaiting_input`, `awaiting_witness`, `awaiting_external` |
| `continuation_tools` | if `allowed` | MCP tool names that resume a checkpointed run (e.g. `continue_run`) |
| `checkpoint_after_each_stage` | yes | Default `true`; run state persisted after every completed stage |

When `allowed` is `false`, the constellation is synchronous-only (no durable
pause). When `allowed` is `true`, pause MUST checkpoint and release any worker
or MCP lease immediately (see `lease_rule`).

Orrery MUST NOT retain the caller's plan text, chat, or unstructured intent as
the source of truth for resume—only checkpointed run state and typed
`action_request` payloads ([#153](https://github.com/lbliii/orrery/issues/153)).

### 4. `composite_receipt_fields`

Describes the terminal composite receipt agents should expect. Fields listed here
MUST appear on completed runs unless the run ends in a pre-terminal failure
disposition.

| Field | Required | Meaning |
| --- | --- | --- |
| `chain` | yes | Always `signed-envelope-chain` |
| `disposition` | yes | Terminal sealed outcome; value from card `dispositions` |
| `policy_digest` | yes | Digest of the frozen graph (stages + edges + release identity) |
| `cites` | no | Array of lowercase hex `sha256` decision digests per [ADR 0006](./0006-decision-receipt.md) |
| `release` | yes | Object `{ "digest": "<hex>", "key_id": "<id>" }` for composite signing |

`cites` is optional per run but REQUIRED in this schema when a stage bound a
DecisionReceipt freeze. Missing cite when policy required one is a
constellation policy failure, not an Envelope verify failure (ADR 0006 §3).

Composite receipts MAY also embed protocol-star digests from epic
[#238](https://github.com/lbliii/orrery/issues/238) in the envelope chain;
those digests live in `chain`, not in `cites`.

### 5. `lease_rule`

Required string, exactly:

```text
waiting_never_holds_worker_lease
```

Normative meaning:

1. Paused or waiting runs MUST NOT hold an HTTP request, MCP worker slot, or
   agent lease open.
2. Resume happens only through authenticated, idempotent continuation tools
   named in `pause_policy.continuation_tools`.
3. Waiting is durable state + typed requests—not blocking polling on Orrery.

Migration [#164](https://github.com/lbliii/orrery/issues/164) and resumable
[#157](https://github.com/lbliii/orrery/issues/157) both inherit this rule
without redefining it.

### 6. Exposure (`gaze_describe` / `explain_policy`)

Constellation cards and `explain_policy` responses MUST include:

```json
{
  "run_contract": { "...": "..." },
  "graph_summary": "...",
  "dispositions": ["ready", "not-ready", "..."],
  "member_stars": [{ "name": "...", "role": "..." }],
  "subtree_contract": {
    "stages": ["..."],
    "pause_policy": { "...": "..." },
    "composite_receipt_fields": { "...": "..." },
    "lease_rule": "waiting_never_holds_worker_lease"
  }
}
```

`gaze_describe` returns the full agent card (including `subtree_contract`).
`explain_policy` returns the same subtree fields in its signed envelope payload.

### 7. Non-goals

- Durable DAG / workflow engine inside Orrery
- Orrery as planner or plan-text host
- Swarm VCS, merge reconciler, or megafile decomposer (ADR 0004/0005)
- New MCP verbs beyond what resumable design [#152](https://github.com/lbliii/orrery/issues/152)/[#153](https://github.com/lbliii/orrery/issues/153) already propose

## Consequences

- Design [#243](https://github.com/lbliii/orrery/issues/243) closes on this ADR;
  workers MUST NOT re-decide field names or lease semantics.
- New constellation leaves ([#213](https://github.com/lbliii/orrery/issues/213)–[#216](https://github.com/lbliii/orrery/issues/216),
  [#154](https://github.com/lbliii/orrery/issues/154), [#245](https://github.com/lbliii/orrery/issues/245))
  publish `subtree_contract` on their agent cards.
- Resumable epic [#157](https://github.com/lbliii/orrery/issues/157) aligns
  pause/continuation MCP to `pause_policy` and `lease_rule`. Durable
  checkpoint store, TTL, and `continue_run` idempotency are frozen in
  design [#152](https://github.com/lbliii/orrery/issues/152) /
  [constellation-run-checkpoint.md](../design/constellation-run-checkpoint.md).
- Migration [#164](https://github.com/lbliii/orrery/issues/164) is a vertical
  instance; shared names live here, not in migration-only prose.
- A follow-on leaf wires `subtree_contract` into existing cards and
  `explain_policy` output; that leaf cites this ADR for field names.

## Examples (representable)

1. **Synchronous content-readiness (#213):** `pause_policy.allowed = false`,
   five `stages`, `composite_receipt_fields.disposition` ∈
   `{ready, needs-work, inconclusive}`.
2. **Resumable board-memo (#154):** `pause_policy.allowed = true`,
   `modes = ["awaiting_input"]`, `continuation_tools = ["continue_run"]`,
   mid-graph `pause` stage before composite seal.
3. **Decision-gated migration (#164):** `cites` includes a DecisionReceipt
   digest for an unsupported-semantics choice; `lease_rule` unchanged.
