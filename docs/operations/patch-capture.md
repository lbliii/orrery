# Patch Capture

`orrery/patch-capture` compares before/after caller file snapshots (or manifest
pairs) and seals a `patch_digest` with changed paths and line stats. Optional
`content` fields enable line accounting; raw bytes are never echoed in the
receipt.

## Inputs

| Field | Required | Notes |
| --- | --- | --- |
| `before.files[]` | yes | `{ path, sha256, size, content? }` |
| `after.files[]` | yes | Same shape |

`content` is optional/private input used only for line stats.

## Outputs

| Field | Meaning |
| --- | --- |
| `patch_digest` | Stable digest over changed-path rows (no content) |
| `changed_paths` | Sorted union of added/removed/modified |
| `added_paths` / `removed_paths` / `modified_paths` | Path partitions |
| `line_stats` | `{ added, removed }` line counts |
| `before_manifest_digest` / `after_manifest_digest` | Side manifests |

## Direct MCP

`POST /stars/patch-capture/mcp` — tool `capture`.

## Ops

- No egress; pure transform over caller bytes.
- Publisher key env: `ORRERY_PATCH_CAPTURE_KEY_ID` (or shared `ORRERY_STAR_*`).
- Acceptance: `uv run pytest tests/stars/test_patch_capture.py -q`
- **Deferral:** Agent Card / gaze intents ("capture patch receipt") deferred
  pending catalog carve-out (epic #238).
