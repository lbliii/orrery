# Docs MyST Inventory

`orrery/docs-myst-inventory` parses a bounded MyST/Markdown documentation tree
and emits a deterministic inventory aligned with ADR 0008 analyze-stage fields.
Callers supply path/content entries locally; the star returns digests and
classified findings without echoing raw repository bytes by default.

## Inputs

| Field | Required | Notes |
| --- | --- | --- |
| `entries[]` | yes | ≤256 files, each ≤256 KiB UTF-8 after NFC |
| `entries[].path` | yes | Repo-relative path, unique within the call |
| `entries[].content` | yes | MyST/Markdown source text |

## Outputs

| Field | Meaning |
| --- | --- |
| `source_manifest_digest` | Content-addressed manifest over sorted `{path, content_digest}` |
| `findings[]` | `feature_id`, ADR 0008 `class`, `path`, optional `span`, `finding_digest` |
| `inventory_digest` | Digest over manifest + sorted findings (alias `analysis_digest`) |

Feature classes are limited to `safe`, `transformable`, `decision_required`,
`unsupported`, and `malformed` — no parallel enums.

## Direct MCP

`POST /stars/docs-myst-inventory/mcp` — tool `inventory`.

## Ops

- No egress; agent-local tree bytes stay with the caller.
- Publisher key env: `ORRERY_DOCS_MYST_INVENTORY_KEY_ID` (or shared `ORRERY_STAR_*`).
- Acceptance: `uv run pytest tests/stars/test_docs_myst_inventory.py -q`
