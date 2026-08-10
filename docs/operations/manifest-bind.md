# Manifest Bind

`orrery/manifest-bind` seals a caller-supplied file inventory into a signed
Envelope. Callers pass `{ path, sha256, size }` rows; Orrery never opens a
repository. Admitted rows are sorted by path and hashed into a stable
`manifest_digest` (lowercase hex sha256 of canonical JSON).

## Inputs

| Field | Required | Notes |
| --- | --- | --- |
| `files[]` | yes | ≤10_000 entries |
| `files[].path` | yes | Relative path; no traversal |
| `files[].sha256` | yes | 64-char lowercase hex |
| `files[].size` | yes | Non-negative integer byte size |

Malformed or duplicate-path entries are excluded (counted) rather than failing
the whole call when at least the list shape is valid.

## Outputs

| Field | Meaning |
| --- | --- |
| `manifest_digest` | Stable digest over sorted admitted rows |
| `admitted_count` / `excluded_count` | Counts |
| `admitted` / `excluded` | Admitted rows / exclusion reasons |

## Direct MCP

`POST /stars/manifest-bind/mcp` — tool `bind`.

## Ops

- No egress; pure seal over caller bytes.
- Publisher key env: `ORRERY_MANIFEST_BIND_KEY_ID` (or shared `ORRERY_STAR_*`).
- Acceptance: `uv run pytest tests/stars/test_manifest_bind.py -q`
- **Deferral:** Agent Card / gaze intent fixtures live in `catalog/agent_card.py`
  and `tests/gaze-intents.v1.json` (outside this leaf's owned paths; epic #238
  allows documented deferrals until a catalog carve-out).
