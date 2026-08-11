# Design: Durable constellation run checkpoint

- **Status:** Accepted (planner freeze)
- **Date:** 2026-08-11
- **Design issue:** [#152](https://github.com/lbliii/orrery/issues/152)
- **Parent epic:** [#157](https://github.com/lbliii/orrery/issues/157)
- **Also informs:** [#240](https://github.com/lbliii/orrery/issues/240), migration [#164](https://github.com/lbliii/orrery/issues/164)
- **Binds:** [ADR 0007](../adr/0007-constellation-subtree-contract.md), closed design [#153](https://github.com/lbliii/orrery/issues/153)

## Question frozen

Where and how is constellation run state persisted across durable pauses so
resume is idempotent, lease-free, and restart-safe — without Orrery becoming
a workflow engine?

## Decision

Adopt **checkpointed run record** (option 3 on #152). Chat transcript and
held MCP/HTTP leases remain rejected (ADR 0007 `lease_rule`).

### 1. Run states (normative)

```text
queued → running → (awaiting_input | awaiting_witness | awaiting_external)
       → running → completed | failed | cancelled | expired
```

Waiting modes are exactly ADR 0007 / #153. Checkpoint after every completed
stage when `pause_policy.checkpoint_after_each_stage` is true (ADR default).

### 2. Concrete store

| Choice | Decision |
| --- | --- |
| Kind | **Control-plane run table** (same plane as `runs/` managed jobs) — not caller chat, not publisher data plane |
| Record body | Structured checkpoint JSON: graph position, stage receipt digests, outstanding `action_request`s, disposition |
| Large payloads | **Content-addressed sealed blobs** by digest only (step receipts / artifacts); default checkpoint omits raw sensitive bytes |
| Process demo | In-memory `ConstellationRunStore` OK for dogfood if it implements the same keying + idempotency rules; durable SQL/backend is a follow-on without renaming fields |

Replace today's process-dict in `catalog/constellation_run.py` with an explicit
store API; do not grow a second parallel state machine.

### 3. Checkpoint verification bind

Every checkpoint MUST include:

| Field | Meaning |
| --- | --- |
| `policy_digest` | Digest of frozen graph (stages + edges + release identity) per ADR 0007 |
| `release` | `{ "digest": "<hex>", "key_id": "<id>" }` expected for composite seal |
| `constellation` | Canonical name |
| `graph_position` | Current / next stage id |
| `stage_receipt_digests` | Ordered digests of completed stage envelopes |
| `outstanding_action_requests` | Typed #153 requests (digests preferred over raw context) |

Resume MUST refuse to continue when caller-supplied or stored `policy_digest`
/ `release.digest` disagree with the live card's frozen graph (stale policy).

### 4. Idempotency key scope for `continue_run`

Replay key (unique):

```text
(caller_id, run_id, request_id, payload_digest)
```

Where `payload_digest = sha256(canonical_json(action_request response payload))`
and `request_id` is the outstanding `action_request.request_id`.

Rules:

- Duplicate `continue_run` with the same replay key returns the **same**
  checkpoint / terminal composite — MUST NOT mint a second composite result
  or artifact.
- Same `(caller_id, run_id, request_id)` with a **different** `payload_digest`
  ⇒ `replay_incompatible` (fail closed).
- `status(run_id)` is read-only and not part of the replay key.

Mirror the sealed-stage pattern in `MigrationRunStore` (`replay_incompatible`).

### 5. Cancellation, expiry, retention

| Disposition | Trigger | Retention default |
| --- | --- | --- |
| `cancelled` | Authenticated `cancel(run_id)` (#153) | Checkpoint retained **30 days**, then deleteable |
| `expired` | `action_request.expires_at` passed with no valid continue | Same as cancelled |
| `completed` / `failed` | Terminal seal or hard failure | Checkpoint + artifact digests **30 days** (align managed-run artifact cleanup knobs where present) |
| Waiting (`awaiting_*`) | Active pause | Outstanding requests honor their `expires_at`; run flips to `expired` when the last request expires |

Defaults are product v1 knobs (env/config may shorten, not silently lengthen
past 90 days without a new design). Waiting never holds a worker/MCP/HTTP
lease.

### 6. Non-goals

- Durable DAG / general workflow engine
- Webhooks/SSE as source of truth for resume
- Plan-text or chat as checkpoint
- New MCP verbs beyond #153 (`status`, `continue_run`, `cancel`)

## What leaves may assume

- [#154](https://github.com/lbliii/orrery/issues/154) board-memo dogfood may
  implement pause/resume against this store + ADR 0007 Example 2 without
  inventing mode names or verbs.
- Migration decision-gated work (#164 / #178–#180) cites this freeze for
  pause persistence; constellation graph designs may still block those leaves.
- Leaves cite this note + ADR 0007 + #153; they do not re-decide store shape.

## ADR

No new ADR — persistence choices live here and in #152; amend ADR 0007 only
if field names must change (they must not for v1).
