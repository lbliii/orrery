# Docs Frontmatter / Link / Asset Migrate

`orrery/docs-frontmatter-link-asset-migrate` applies explicit profile rules to
caller-supplied documentation bytes: rename frontmatter fields, rewrite
internal links and anchors, and classify asset references. It returns a
bounded unified-diff patch plus a before/after link/asset report. Remote URL
fetch and external asset copy stay denied unless `execution_grants` includes
`fetch_remote_urls` / `copy_external_assets` (still no network I/O from this
star).

## Inputs

| Field | Required | Notes |
| --- | --- | --- |
| `entries[]` | yes | ≤256 files, each ≤256 KiB UTF-8 after NFC |
| `entries[].path` | yes | Repo-relative path; traversal rejected |
| `entries[].content` | yes | Markdown/MyST source text |
| `rules` | no | Profile rules object (defaults preserve) |
| `rules.field_renames` | no | Frontmatter key → new key |
| `rules.path_redirects` | no | Canonical path → redirected path |
| `rules.anchor_redirects` | no | Anchor slug → redirected slug |
| `rules.supported_asset_extensions` | no | Default image/pdf set |
| `rules.execution_grants` | no | Empty by default; no egress |

## Outputs

| Field | Meaning |
| --- | --- |
| `source_manifest_digest` | Content-addressed source inventory |
| `rules_digest` | Digest of normalized rules |
| `file_entries[]` | Per-path `source_digest` / `target_digest` / `changed` |
| `patch` | Bounded unified diffs (`files[]`, `truncated`) |
| `patch_digest` | Digest over patch metadata |
| `report.links` / `report.frontmatter` | Before/after + status |
| `findings[]` | ADR 0008 classes with `finding_digest` |
| `migrate_digest` | Digest-bound result (excludes raw target bytes) |
| `targets[]` | Changed file contents for local apply / independent diff |

Statuses include `preserved`, `renamed`, `rewritten`, `redirect`,
`unresolved`, `external`, `external_granted`, `unsafe`, and `unsupported`.

## Direct MCP

`POST /stars/docs-frontmatter-link-asset-migrate/mcp` — tool `migrate`.

## Ops

- No egress; agent-local tree bytes stay with the caller.
- Publisher key env: `ORRERY_DOCS_FRONTMATTER_LINK_ASSET_MIGRATE_KEY_ID`
  (or shared `ORRERY_STAR_*`).
- Acceptance:
  `uv run pytest tests/stars/test_docs_frontmatter_link_asset_migrate.py -q`
