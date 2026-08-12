# Decision Bind

`orrery/decision-bind` seals a bounded planner decision into a signed Envelope
whose result carries a **DecisionReceipt** (ADR 0006). Callers supply a stable
`decision_id` and the exact UTF-8 decision text; the star returns
`decision_digest` as lowercase hex `sha256` of the statement after NFC
normalization only.

## Inputs

| Field | Required | Notes |
| --- | --- | --- |
| `decision_id` | yes | Caller id (≤128 chars) |
| `statement` | yes | Decision text (≤16 KiB UTF-8 after NFC) |
| `adr_url` | no | HTTPS URL to an external ADR |
| `issue_url` | no | HTTPS URL to a tracker issue |

## Verify (offline)

1. Verify the Envelope signature per
   [envelope-verification.md](../verification/envelope-verification.md).
2. Recompute `sha256(NFC UTF-8 statement)` and compare to `decision_digest`.
3. Reject empty or oversized statements.

Constellation composite receipts cite `decision_digest` values in a `cites`
array; fetching statement text from Orrery is not supported in v1. Host-sealed
success envelopes include a signed `payload.via` attribution object (design #317).

## Direct MCP

`POST /stars/decision-bind/mcp` — tool `bind`.

## Ops

- No egress; pure seal at call time.
- Publisher key env: `ORRERY_DECISION_BIND_KEY_ID` (or shared `ORRERY_STAR_*`).
- Acceptance: `uv run pytest tests/stars/test_decision_bind.py -q`
