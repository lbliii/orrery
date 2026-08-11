# Design: API-spec upgrade constellation graph

- **Status:** Accepted (planner freeze)
- **Date:** 2026-08-11
- **Parent epic:** [#164](https://github.com/lbliii/orrery/issues/164)
- **Implements leaf:** [#179](https://github.com/lbliii/orrery/issues/179)
- **Binds:** ADR 0007, ADR 0008, closed [#152](https://github.com/lbliii/orrery/issues/152)/[#153](https://github.com/lbliii/orrery/issues/153),
  docs path sibling [#178](https://github.com/lbliii/orrery/issues/178)

## Question frozen

What fixed stage graph may `api-spec/upgrade` assume so a worker does not invent
migration topology, pause verbs, or collapse validation into compatibility?

## Decision

One **frozen** constellation. Reuse shipped API-spec migration stars. Distinguish
**target-schema validity** (validate) from **declared compatibility**
(compatibility-diff). A typed approval records a **policy exception** — it MUST
NOT rewrite compatibility evidence digests.

### Stages (normative order)

| # | Stage id | Role | Star ref (consume sealed shapes) |
| --- | --- | --- | --- |
| 1 | `inventory` | gate | `orrery/api-spec-openapi-inventory` |
| 2 | `choose-profile` | gate | ADR 0008 pinned upgrade/compatibility profile (fixtures; no parallel schema) |
| 3 | `safe-upgrade` | gate | `orrery/api-spec-openapi-upgrade-safe` (change bundle) |
| 4 | `breaking-approval` | pause | Typed `action_request` (#153) when breaking/unknown/decision-required findings exist; mode `awaiting_input` |
| 5 | `validate-target` | gate | `orrery/api-spec-openapi-validate` (schema conformance only) |
| 6 | `compatibility-diff` | gate | `orrery/api-spec-compatibility-diff` (policy classification; never claims runtime compatibility) |
| 7 | `artifact-seal` | composite | Composite Envelope per ADR 0007 |

Edges are linear 1→…→7. Stage 4 is skipped when inventory/upgrade-safe emit no
breaking/unknown/decision-required findings requiring human policy exception.

### Pause / resume

- `pause_policy.allowed = true`
- `modes = ["awaiting_input"]`
- `continuation_tools = ["continue_run"]` (+ `status`, `cancel` per #153)
- Checkpoint / idempotency / TTL: #152 /
  `docs/design/constellation-run-checkpoint.md`
- Waiting never holds a worker lease

### Receipt / non-goals

Terminal receipt binds: profile digest, source/target digests, change-bundle
digest, validation digest, compatibility-diff digest, optional decision cites
(ADR 0006). Default receipts omit raw private source bytes.

**Approval semantics:** scoped exception is recorded as a DecisionReceipt cite or
bounded decision metadata — compatibility-diff output digests remain the
structural evidence and are not rewritten to “look compatible.”

**Not now:** local Git/PR handoff (#180), docs migrate graph (#178 already
shipped), inventing new MCP verbs, claiming runtime compatibility from
structural equality.

## What leaf #179 may assume

- Package under `stars/` (e.g. `stars/api_spec_upgrade/`) matching the agent card
- Register card + policy graph only; consume sealed outputs from inventory /
  upgrade-safe / validate / compatibility-diff — do not reimplement
- Carve-outs: `catalog/constellation.py`, `catalog/agent_card.py`,
  `catalog/constellation_run.py`, `stars/builtins.py`, `catalog/coverage.py`
