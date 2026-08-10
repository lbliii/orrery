# Docs RST Inventory

`orrery/docs-rst-inventory` parses a bounded reStructuredText/Sphinx documentation
tree and emits a deterministic inventory aligned with ADR 0008 analyze-stage
fields. Callers supply path/content entries locally; the star returns digests and
classified findings without echoing raw repository bytes by default.

This star does **not** convert RST to MDX. It classifies constructs so callers
can decide whether automatic conversion is eligible.

## Inputs

| Field | Required | Notes |
| --- | --- | --- |
| `entries[]` | yes | ≤256 files, each ≤256 KiB UTF-8 after NFC |
| `entries[].path` | yes | Repo-relative path, unique within the call |
| `entries[].content` | yes | RST source text |

## Outputs

| Field | Meaning |
| --- | --- |
| `source_manifest_digest` | Content-addressed manifest over sorted `{path, content_digest}` |
| `findings[]` | `feature_id`, ADR 0008 `class`, `path`, optional `span`, `finding_digest` |
| `inventory_digest` | Digest over manifest + sorted findings (alias `analysis_digest`) |
| `conversion_eligible` | `true` only when no `decision_required` / `unsupported` / `malformed` findings |
| `ineligibility_reasons` | Compact blocking findings explaining why conversion is not eligible |

Feature classes are limited to `safe`, `transformable`, `decision_required`,
`unsupported`, and `malformed` — no parallel enums.

Representative Sphinx surfaces covered: directives (admonitions, include,
toctree, autodoc, raw, tables, custom), roles, substitutions, section titles,
and image assets.

## Direct MCP

`POST /stars/docs-rst-inventory/mcp` — tool `inventory`.

## Ops

- No egress; agent-local tree bytes stay with the caller.
- Publisher key env: `ORRERY_DOCS_RST_INVENTORY_KEY_ID` (or shared `ORRERY_STAR_*`).
- Package follows the same layout as `docs_myst_inventory` (not registered in
  `stars/builtins.py`).
- Acceptance: `uv run pytest tests/stars/test_docs_rst_inventory.py -q`
