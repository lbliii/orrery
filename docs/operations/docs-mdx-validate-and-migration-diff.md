# Docs MDX Validate and Migration Diff

`orrery/docs-mdx-validate-and-migration-diff` runs the pinned MDX
validator/build adapter against caller-held target bytes and compares the
source inventory to the generated target inventory. It seals an ADR 0008
`validation` stage for a sealed `change_bundle` and emits bounded
migration-diff evidence. It does **not** claim runtime/framework
compatibility.

Consumes sealed plan/bundle shapes from:

- `orrery/docs-myst-to-mdx-safe` (#170) — `plan` / `apply` → `change_bundle`
- `orrery/docs-frontmatter-link-asset-migrate` (#171) — optional
  `link_asset_report` for unresolved links/assets
- `orrery/docs-myst-inventory` (#169) — source inventory classification

## Tool

| Tool | Input | Output |
| --- | --- | --- |
| `validate` | `source_entries[]`, `target_entries[]`, sealed `change_bundle`, pinned `profile`; optional sealed `plan`, `link_asset_report` | ADR 0008 `validation`, `migration_diff`, digests |

`change_bundle.bundle_digest` is recomputed and rejected on mismatch. When
`plan` is supplied, `plan_digest` must match the bundle.

## Migration-diff evidence

| Field | Meaning |
| --- | --- |
| `build_status` | Target MDX adapter pass/fail + finding count |
| `dropped_constructs` | Source constructs without target equivalents |
| `added_constructs` | Unexpected MDX constructs |
| `unresolved_links` / `unresolved_assets` | From optional #171 report |
| `mapping_coverage` | Source paths covered by `change_bundle.file_entries` |
| `report_digest` | Receipt-attachable digest over bounded report body |

Semantic-loss findings stay visible even when syntax build passes
(`severity: informational`, `action: report`). Syntax/build failures seal
`validation_passed: false` (breaking / block). Diagnostics never include raw
source or target bytes.

## Direct MCP

`POST /stars/docs-mdx-validate-and-migration-diff/mcp` — tool `validate`.

Package follows the same layout as sibling docs migration stars (not
registered in `stars/builtins.py` in this leaf).

## Ops

- No egress; agent-local tree bytes stay with the caller.
- Publisher key env: `ORRERY_DOCS_MDX_VALIDATE_AND_MIGRATION_DIFF_KEY_ID`
  (or shared `ORRERY_STAR_*`).
- Acceptance:
  `uv run pytest tests/stars/test_docs_mdx_validate_and_migration_diff.py -q`
