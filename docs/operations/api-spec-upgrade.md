# API-spec upgrade (constellation)

`orrery/api-spec-upgrade` is a **frozen** OpenAPI migration constellation (#179):
inventory → profile pin → safe upgrade → optional breaking-approval pause →
validate-target → compatibility-diff → composite migration receipt. It **consumes**
sealed outputs from existing API-spec migration stars — it does not reimplement
them.

## Stage graph

| Stage | Star / role |
| --- | --- |
| `inventory` | `orrery/api-spec-openapi-inventory` |
| `choose-profile` | pinned ADR 0008 `MigrationProfile` |
| `safe-upgrade` | `orrery/api-spec-openapi-upgrade-safe` (`plan` + `apply`) |
| `breaking-approval` | pause when breaking/unknown/decision-required findings remain |
| `validate-target` | `orrery/api-spec-openapi-validate` (schema conformance only) |
| `compatibility-diff` | `orrery/api-spec-compatibility-diff` (policy classification) |
| `artifact-seal` | composite `migration-receipt/v1` + Envelope chain |

Stage 4 is skipped when inventory/safe-upgrade emit no
breaking/unknown/decision-required findings requiring human policy exception.

**Target-schema validity** (`validate-target`) stays distinct from **declared
compatibility** (`compatibility-diff`). Typed approvals record policy exceptions
via DecisionReceipt cites — they do not rewrite compatibility-diff digests.

## Tools

| Tool | Role |
| --- | --- |
| `run` | Start run; may pause with one typed `action_request` |
| `status` | Read disposition, graph position, outstanding requests |
| `continue_run` | Idempotent resume; seals validate + diff + composite receipt |
| `cancel` | Terminal `cancelled` disposition |

Pause uses `awaiting_input` only (#153). Waiting never holds a worker/MCP lease
(ADR 0007 `lease_rule`).

## Receipt contract

Terminal composite binds: `profile_digest`, `source`/`target`, `transformer`/
`validator`, `source_manifest_digest`, `output_manifest_digest`, `bundle_digest`,
`validation_digest`, `compatibility_diff_digest` (distinct from validate),
optional `cites`, and ADR 0008 `migration_receipt`. Default receipts omit raw
source/target bytes (`retention_redaction`).

Duplicate `continue_run` with the same response replays the same composite —
no second patch. Incompatible late responses are rejected (`replay_incompatible`).

## Direct MCP

`POST /constellations/api-spec-upgrade/mcp`

Publisher key env: `ORRERY_API_SPEC_UPGRADE_KEY_ID` (or shared `ORRERY_STAR_*`).

## Acceptance

```bash
uv run pytest tests/stars/test_api_spec_upgrade.py -q
uv run ruff check .
```
