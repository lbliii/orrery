# API Spec OpenAPI Validate

`orrery/api-spec-openapi-validate` runs the pinned OpenAPI parser/schema
adapter against caller-held target bytes and an optional sealed `change_bundle`
from `orrery/api-spec-openapi-upgrade-safe`. It emits ADR 0008 validation stage
artifacts with tool identity, pass/fail, bounded diagnostics, and findings.

Validation proves **target-schema conformance only**. Compatibility conclusions
remain with `orrery/api-spec-compatibility-diff` (#176).

## Inputs

| Field | Required | Notes |
| --- | --- | --- |
| `target_entries[]` | yes | ≤256 files, each ≤256 KiB UTF-8 after NFC |
| `change_bundle` | yes | ADR 0008 apply artifact; `bundle_digest` verified |
| `profile` | yes | Pinned `MigrationProfile`; validator name must match |
| `source_entries[]` | no | When supplied, paths must align with targets |
| `plan` | no | When supplied, `plan_digest` must match bundle |

## Findings

| Kind | Shape | When |
| --- | --- | --- |
| Schema | `feature_id`, `class`, `path`, `message`, `finding_digest` | JSON/OpenAPI 3.1 parse or lint failure |
| Policy block | `id`, `severity`, `action`, `path`, `message`, `finding_digest` | Sealed plan includes blocked `remove_path` under `breaking.path.remove` |

Diagnostics are redacted/bounded via `stars/_core/migration_validate.py`
(#167). Raw source/target bytes never appear by default.

Validator failure or blocking findings force `validation_passed: false`; a
previously sealed failed validation cannot be overwritten as success (replay
store rejects incompatible digests).

## Direct MCP

`POST /stars/api-spec-openapi-validate/mcp` — tool `validate`.

Package layout matches sibling api-spec stars (star.toml-only; not registered in
`stars/builtins.py` in this leaf).

## Ops

- No egress; agent-local document bytes stay with the caller.
- Publisher key env: `ORRERY_API_SPEC_OPENAPI_VALIDATE_KEY_ID` (or shared
  `ORRERY_STAR_*`).
- Acceptance:
  `uv run pytest tests/stars/test_api_spec_openapi_validate.py -q`
