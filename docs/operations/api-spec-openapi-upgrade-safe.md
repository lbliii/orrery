# API Spec OpenAPI Upgrade (safe)

`orrery/api-spec-openapi-upgrade-safe` plans and applies a **pinned** OpenAPI
`3.0.3` → `3.1.0` upgrade under ADR 0008 MigrationProfile
`api-spec/openapi-3-0-to-3-1-safe`. Callers supply path/content entries locally.
`apply` returns a sealed `change_bundle` plus target bytes — it never mutates a
source checkout and never accepts a floating `latest` profile.

Inventory classification is consumed from `orrery/api-spec-openapi-inventory`
(#174).

## Corpus subset (pinned profile)

| Feature id | Class | Op |
| --- | --- | --- |
| `openapi.json_schema.draft2020` | transformable | `bump_openapi` `3.0.3`→`3.1.0` |
| `openapi.nullable` | transformable | `transform_nullable` → JSON Schema 2020-12 `type` unions |
| safe constructs (`openapi.version`, schemas, ops, …) | safe | `copy_construct` |

Unsupported / decision-required / malformed constructs (discriminator mapping,
vendor `x-*` extensions, external `$ref`, …) become **findings** and `hold`
ops. Source bytes are preserved — never silently rewritten as equivalent.

## Tools

| Tool | Input | Output |
| --- | --- | --- |
| `plan` | `entries[]`, pinned `profile` | ADR 0008 `plan` + findings + digests |
| `apply` | `entries[]`, sealed `plan`, `profile` | `change_bundle`, `targets[]`, findings |

`apply` rejects plans whose `analysis_digest` / `source_manifest_digest` or
`profile_digest` do not match the supplied entries and profile (idempotent on
compatible replay).

## Direct MCP

`POST /stars/api-spec-openapi-upgrade-safe/mcp` — tools `plan`, `apply`.

Package follows the same layout as `api_spec_openapi_inventory` (not registered
in `stars/builtins.py` in this leaf).

## Ops

- No egress; agent-local document bytes stay with the caller.
- Publisher key env: `ORRERY_API_SPEC_OPENAPI_UPGRADE_SAFE_KEY_ID` (or shared
  `ORRERY_STAR_*`).
- Target parse stub lives in-package until `api-spec/openapi-validate` (#177).
- Acceptance:
  `uv run pytest tests/stars/test_api_spec_openapi_upgrade_safe.py -q`
