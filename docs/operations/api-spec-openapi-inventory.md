# API Spec OpenAPI Inventory

`orrery/api-spec-openapi-inventory` parses bounded OpenAPI JSON document
entries and emits a deterministic inventory aligned with ADR 0008 analyze-stage
fields. Callers supply path/content entries locally; the star returns digests
and classified findings without fetching external `$ref` targets or claiming a
semantic upgrade.

## Inputs

| Field | Required | Notes |
| --- | --- | --- |
| `entries[]` | yes | ≤256 files, each ≤256 KiB UTF-8 after NFC |
| `entries[].path` | yes | Repo-relative path, unique within the call |
| `entries[].content` | yes | OpenAPI JSON source text |
| `ref_policy` | no | Defaults to `{ "mode": "deny_external" }` |

### `ref_policy`

| Mode | Meaning |
| --- | --- |
| `deny_external` | HTTP(S) `$ref` → `decision_required` (never fetched) |
| `allow_prefixes` | Requires `allowed_prefixes[]`; in-scope URIs still not fetched |

## Outputs

| Field | Meaning |
| --- | --- |
| `source` | Declared `{ kind, version }` when parse succeeds |
| `source_manifest_digest` | Content-addressed manifest over sorted `{path, content_digest}` |
| `findings[]` | `feature_id`, ADR 0008 `class`, `path`, optional `span`, `finding_digest` |
| `inventory_digest` | Digest over manifest + source + sorted findings (alias `analysis_digest`) |

Feature classes are limited to `safe`, `transformable`, `decision_required`,
`unsupported`, and `malformed` — no parallel enums.

Profile-relevant examples: `openapi.json_schema.draft2020` (transformable on
3.0.x) and `openapi.discriminator.mapping` (unsupported).

## Direct MCP

`POST /stars/api-spec-openapi-inventory/mcp` — tool `inventory`.

Package layout matches `docs_myst_inventory` (star.toml-only; not registered in
`stars/builtins.py` in this leaf).

## Ops

- No egress; agent-local document bytes stay with the caller.
- Publisher key env: `ORRERY_API_SPEC_OPENAPI_INVENTORY_KEY_ID` (or shared
  `ORRERY_STAR_*`).
- Acceptance: `uv run pytest tests/stars/test_api_spec_openapi_inventory.py -q`
