# Docs MyST → MDX (safe)

`orrery/docs-myst-to-mdx-safe` plans and applies a **corpus-backed** MyST subset
to baseline MDX under a pinned ADR 0008 MigrationProfile. Callers supply
path/content entries locally. `apply` returns a sealed `change_bundle` plus
target bytes — it never mutates a source checkout.

Inventory classification is consumed from `orrery/docs-myst-inventory` (#169).

## Corpus subset (baseline profile)

| Feature id | Class | Op |
| --- | --- | --- |
| `md.heading` | safe | `copy_heading` |
| `myst.directive.admonition` | transformable | `transform_admonition` → `<Admonition type="…">` |

Unsupported / decision-required / malformed constructs become **findings** and
`hold` ops. Their source syntax is preserved — never silently rendered as plain
text.

## Tools

| Tool | Input | Output |
| --- | --- | --- |
| `plan` | `entries[]`, pinned `profile` | ADR 0008 `plan` + findings + digests |
| `apply` | `entries[]`, sealed `plan`, `profile` | `change_bundle`, `targets[]`, findings |

`apply` rejects plans whose `analysis_digest` / `source_manifest_digest` or
`profile_digest` do not match the supplied entries and profile (idempotent on
compatible replay).

## Direct MCP

`POST /stars/docs-myst-to-mdx-safe/mcp` — tools `plan`, `apply`.

Package follows the same layout as `docs_myst_inventory` (not registered in
`stars/builtins.py` in this leaf).

## Ops

- No egress; agent-local tree bytes stay with the caller.
- Publisher key env: `ORRERY_DOCS_MYST_TO_MDX_SAFE_KEY_ID` (or shared `ORRERY_STAR_*`).
- Baseline MDX buildability stub lives in-package until `docs/mdx-validate` (#172).
- Acceptance: `uv run pytest tests/stars/test_docs_myst_to_mdx_safe.py -q`
