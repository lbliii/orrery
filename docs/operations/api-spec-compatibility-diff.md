# API Spec Compatibility Diff

`orrery/api-spec-compatibility-diff` compares caller-held source and candidate
target OpenAPI JSON entries under a declared ADR 0008 `compatibility_policy`.
It classifies structural changes, emits stable operation/schema JSON Pointer
paths, and seals digests for receipt use.

**It never claims that structural equality implies runtime compatibility.**
`runtime_compatibility_claimed` is always `false`.

## Inputs

| Field | Required | Notes |
| --- | --- | --- |
| `source_entries[]` | yes | ≤256 files, each ≤256 KiB UTF-8 after NFC |
| `target_entries[]` | yes | Same bounds as source |
| `compatibility_policy` | yes | ADR 0008 shape only (no parallel schema) |

### `compatibility_policy` (ADR 0008 §4)

```json
{
  "policy_id": "openapi-client-server-v1",
  "default_action": "report",
  "rules": [
    {"id": "breaking.path.remove", "severity": "breaking", "action": "block"},
    {"id": "info.description.change", "severity": "informational", "action": "allow"}
  ]
}
```

`severity` ∈ `breaking` | `behavioral` | `informational`.  
`action` ∈ `allow` | `report` | `block` | `decision_required`.

## Classifications

| Classification | When |
| --- | --- |
| `breaking` / `behavioral` / `informational` | Matched rule severity (action ≠ `allow`) |
| `policy-exempt` | Matched rule with `action: allow` |
| `additive` | New operation/schema (or additive rule) |
| `unknown` | Ambiguous edits without a matching rule → `decision_required` |

Inventory digests from `orrery/api-spec-openapi-inventory` (#174) bind source
and target manifests; this star does not invent a second policy schema.

## Direct MCP

`POST /stars/api-spec-compatibility-diff/mcp` — tool `diff`.

Package layout matches sibling api-spec stars (star.toml-only; not registered
in `stars/builtins.py` in this leaf).

## Ops

- No egress; agent-local document bytes stay with the caller.
- Publisher key env: `ORRERY_API_SPEC_COMPATIBILITY_DIFF_KEY_ID` (or shared
  `ORRERY_STAR_*`).
- Acceptance:
  `uv run pytest tests/stars/test_api_spec_compatibility_diff.py -q`
