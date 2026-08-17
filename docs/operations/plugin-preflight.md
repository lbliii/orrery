# Plugin Preflight

`orrery/plugin-preflight` seals Agent Plugins 1.0.0 conformance over a
caller-supplied `{path, content}` bundle. Orrery never opens a repository
and never installs or launches a plugin.

Profile is pinned: `agent-plugins/1.0.0`. Schemas are read from the
in-repo pin at `plugins/schemas/1.0.0/` (constants in the contract match
those `$id` values). No egress.

## Inputs

| Field | Required | Notes |
| --- | --- | --- |
| `files[]` | yes | `{path, content}` — plugin root bundle |
| `profile` | no | `agent-plugins/1.0.0` (default) |
| `manifest_digest` | no | Must match the derived bind digest when set |

## Fatal vs skip

Fatal (fails `passed`): `plugin_json_missing`, `plugin_json_invalid`,
`name_invalid`, `schema_unsupported`, `path_escape`.

Non-fatal skip: missing `skills/` or `mcp.json`; `skill_skipped`;
`server_skipped`; `mcp_schema_mismatch` (disables MCP only).

Advisory (does not fail `passed`): `secret_like_header`, `secret_like_env`.

stdio servers that satisfy the spec are **valid**. Listing/sky still
requires HTTPS `streamable-http` (ADR 0012) — that is not this star.

## Direct MCP

`POST /stars/plugin-preflight/mcp` — tool `check`.

## Ops

- No egress; caller bytes only.
- Publisher key env: `ORRERY_PLUGIN_PREFLIGHT_KEY_ID` (or shared `ORRERY_STAR_*`).
- Acceptance: `uv run pytest tests/stars/test_plugin_preflight.py -q`
