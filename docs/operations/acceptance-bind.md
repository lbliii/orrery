# Acceptance Bind

`orrery/acceptance-bind` seals sprint done-criteria plus VerifyRef pointers into
a signed Envelope whose result carries an **AcceptanceReceipt** (ADR 0009).
Callers supply a stable `acceptance_id` and a non-empty `criteria` array; the
star returns `acceptance_digest` as lowercase hex `sha256` of canonical
acceptance bytes. Orrery does **not** execute verify refs in v1.

## Inputs

| Field | Required | Notes |
| --- | --- | --- |
| `acceptance_id` | yes | Caller id (≤128 chars, NFC-normalized) |
| `criteria` | yes | 1-32 criterion objects (sorted by id for digest) |
| `adr_url` | no | HTTPS URL to an external ADR |
| `issue_url` | no | HTTPS URL to a tracker issue |

Each criterion:

| Field | Required | Notes |
| --- | --- | --- |
| `id` | yes | Stable slug (kebab-case, ≤64 chars) |
| `statement` | yes | Exact done text (≤4 KiB UTF-8 after NFC) |
| `verify` | yes | VerifyRef: `kind`, `ref`, optional `expect` |

VerifyRef `kind` values: `pytest`, `command`, `http_smoke`, `envelope_verify`,
`digest_eq`, `external_ref`.

## Verify (offline)

1. Verify the Envelope signature per
   [envelope-verification.md](../verification/envelope-verification.md).
2. Recompute canonical acceptance bytes from persisted `acceptance_id` and
   `criteria` (criteria sorted by id; omit `verify.expect` when absent); compare
   to `acceptance_digest`.
3. Reject empty criteria, duplicate criterion ids, unknown verify kinds, or
   oversized fields.

Constellation composite receipts cite acceptance digests in `acceptance_cites`
(ADR 0007 / 0009), parallel to DecisionReceipt `cites`. Fetching criteria text
from Orrery by digest alone is not supported in v1.

## Direct MCP

`POST /stars/acceptance-bind/mcp` — tool `bind`.

## Ops

- No egress; pure seal at call time.
- Publisher key env: `ORRERY_ACCEPTANCE_BIND_KEY_ID` (or shared `ORRERY_STAR_*`).
- Agent card stamps `tree_role: planner` (informational).
- Acceptance: `uv run pytest tests/stars/test_acceptance_bind.py -q`
