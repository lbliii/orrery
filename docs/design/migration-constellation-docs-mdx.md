# Design: Docs migrate-to-MDX constellation graph

- **Status:** Accepted (planner freeze)
- **Date:** 2026-08-11
- **Parent epic:** [#164](https://github.com/lbliii/orrery/issues/164)
- **Implements leaf:** [#178](https://github.com/lbliii/orrery/issues/178)
- **Binds:** ADR 0007, ADR 0008, closed [#152](https://github.com/lbliii/orrery/issues/152)/[#153](https://github.com/lbliii/orrery/issues/153), board-memo proof [#154](https://github.com/lbliii/orrery/issues/154)

## Question frozen

What fixed stage graph may `docs/migrate-to-mdx` assume so a worker does not
invent migration topology or pause verbs?

## Decision

One **frozen** constellation (not a general authoring IDE). Reuse shipped
migration stars; pause only for unsupported semantics / policy exceptions.

### Stages (normative order)

| # | Stage id | Role | Star ref (consume sealed shapes) |
| --- | --- | --- | --- |
| 1 | `inventory` | gate | `orrery/docs-myst-inventory` (or rst inventory when source is rst) |
| 2 | `choose-profile` | gate | Profile pin from ADR 0008 / migration fixtures (no live rewrite of profile schema) |
| 3 | `safe-convert` | gate | `orrery/docs-myst-to-mdx-safe` + `orrery/docs-frontmatter-link-asset-migrate` as policy requires |
| 4 | `unsupported-decision` | pause | Typed `action_request` (#153); modes ⊆ `awaiting_input` |
| 5 | `validate-diff` | gate | `orrery/docs-mdx-validate-and-migration-diff` |
| 6 | `artifact-seal` | composite | Composite Envelope per ADR 0007 (`policy_digest`, `release`, optional `cites`) |

Edges are linear 1→2→3→4→5→6. Stage 4 is skipped when inventory/safe-convert
emit no decision-required findings.

### Pause / resume

- `pause_policy.allowed = true`
- `modes = ["awaiting_input"]`
- `continuation_tools = ["continue_run"]` (+ `status`, `cancel` per #153)
- Checkpoint / idempotency / TTL: closed #152 /
  `docs/design/constellation-run-checkpoint.md`
- Waiting never holds a worker lease (ADR 0007 `lease_rule`)

### Receipt / non-goals

Terminal receipt binds: profile digest, source/output digests, decision cites
(ADR 0006 when used), validation digest, change-bundle digest. Default receipts
omit raw private source bytes (ADR 0008 retention_redaction).

**Not now:** local Git/PR handoff (#180), API-spec upgrade graph (#179),
general workflow engine, inventing new MCP verbs.

## What leaf #178 may assume

- Package under `stars/` (name at claim matching agent card, e.g.
  `stars/docs_migrate_to_mdx/`)
- Register card + policy graph only; consume existing migration star sealed
  outputs — do not reimplement inventory/convert/validate
- Evolve shared run helpers only via explicit carve-out on
  `catalog/constellation_run.py` if board-memo patterns must be reused
