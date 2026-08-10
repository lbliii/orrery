# Manifest Preflight

`orrery/manifest-preflight` evaluates a caller-supplied file list against a
named versioned policy and returns pass/fail plus violation codes. Use it to
check files before run without Orrery hosting the caller's tree.

## Inputs

| Field | Required | Notes |
| --- | --- | --- |
| `files[]` | yes | Same shape as `orrery/manifest-bind` |
| `policy` | yes | Versioned policy name |
| `manifest_digest` | no | When set, must match the bind digest |

## Policies (v1)

| Policy | Rule | Violation code |
| --- | --- | --- |
| `orrery/docs-only@v1` | Every path under `docs/` with a docs-like suffix | `path_not_docs` |
| `orrery/max-100-files@v1` | At most 100 admitted files | `too_many_files` |

## Outputs

| Field | Meaning |
| --- | --- |
| `passed` | True when `violations` is empty |
| `policy` | Echo of the named policy |
| `manifest_digest` | Digest of the admitted list |
| `violations` / `violation_codes` | Structured + code list |

## Direct MCP

`POST /stars/manifest-preflight/mcp` — tool `check`.

## Ops

- No egress; policies are static named rules.
- Publisher key env: `ORRERY_MANIFEST_PREFLIGHT_KEY_ID` (or shared `ORRERY_STAR_*`).
- Acceptance: `uv run pytest tests/stars/test_manifest_preflight.py -q`
- **Deferral:** Agent Card / gaze intents ("check files before run") deferred
  pending catalog carve-out (epic #238).
