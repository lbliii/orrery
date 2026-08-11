# Docs migrate-to-MDX (constellation)

`orrery/docs-migrate-to-mdx` is a **frozen** migration constellation (#178):
inventory → profile pin → safe convert → optional unsupported-decision pause →
validate-diff → composite migration receipt. It **consumes** sealed outputs from
existing migration stars — it does not reimplement them.

## Stage graph

| Stage | Star / role |
| --- | --- |
| `inventory` | `orrery/docs-myst-inventory` |
| `choose-profile` | pinned ADR 0008 `MigrationProfile` |
| `safe-convert` | `orrery/docs-myst-to-mdx-safe` (`plan` + `apply`) |
| `unsupported-decision` | pause when `decision_required` findings remain |
| `validate-diff` | `orrery/docs-mdx-validate-and-migration-diff` |
| `artifact-seal` | composite `migration-receipt/v1` + Envelope chain |

Stage 4 is skipped when inventory/safe-convert emit no `decision_required` findings.

## Tools

| Tool | Role |
| --- | --- |
| `run` | Start run; may pause with one typed `action_request` |
| `status` | Read disposition, graph position, outstanding requests |
| `continue_run` | Idempotent resume; seals validate + composite receipt |
| `cancel` | Terminal `cancelled` disposition |

Pause uses `awaiting_input` only (#153). Waiting never holds a worker/MCP lease
(ADR 0007 `lease_rule`).

## Receipt contract

Terminal composite binds: `profile_digest`, `source_manifest_digest`,
`output_manifest_digest`, `bundle_digest`, `validation_digest`, optional
`cites` (DecisionReceipt digests), and ADR 0008 `migration_receipt`. Default
receipts omit raw source/target bytes (`retention_redaction`).

Duplicate `continue_run` with the same response replays the same composite —
no second patch. Incompatible late responses are rejected (`replay_incompatible`).

## Direct MCP

`POST /constellations/docs-migrate-to-mdx/mcp`

Publisher key env: `ORRERY_DOCS_MIGRATE_TO_MDX_KEY_ID` (or shared `ORRERY_STAR_*`).

## Acceptance

```bash
uv run pytest tests/stars/test_docs_migrate_to_mdx.py -q
uv run ruff check .
```
