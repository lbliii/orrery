# ADR 0011: Error surfaces (three channels, additive only)

- **Status:** Accepted
- **Date:** 2026-08-14
- **Issues:** epic [#426](https://github.com/lbliii/orrery/issues/426),
  design [#427](https://github.com/lbliii/orrery/issues/427)
- **Depends on:** [0010](./0010-aggregate-mcp-call-skill.md),
  [0002](./0002-prepaid-wallet-ledger.md),
  [0004](./0004-publisher-direct-call.md),
  [0005](./0005-discovery-and-dual-trust.md)
- **Design note:** [caller-trust-a-tier.md](../design/caller-trust-a-tier.md)

## Context

Callers hit Orrery on three boundaries: HTTP JSON, aggregate `/mcp`
(ADR 0010), and signed star Envelope payloads. Each grew a dialect.
`structured_tool_body` wraps unsigned `{error: "not_found"}` as
`status: "ok"`. Managed `submit()` raises while `result()` returns a dict.
`/api/envelope/verify` returns `verified: false` with no machine code.
`call_skill` can leak `str(exc)` on `call_failed`.

Agents that branch on `body.status === "error"` (the ADR 0010 contract)
mis-parse discovery misses as success. That is a product defect, not lint.

## Decision

Keep **three channels**. Do not collapse them. Adapt at the boundary.

### 1. Channel table

| Boundary | Success | Expected failure | Unexpected crash |
| --- | --- | --- | --- |
| HTTP JSON | resource body | `{error: "<code>", ...}` + status | log; `500` / `503` with a **code**, never raw `str(exc)` |
| Aggregate `/mcp` | ADR 0010 `{status:"ok", payload, envelope_wire?}` | `{status:"error", error:{code, message}}` | same; `code` stable, `message` caller-safe |
| Sealed star payload | domain fields | `{error: "<code>", ...}` **inside** signed `payload` | raise in-process; worker logs; do not mint a fake seal |

### 2. Unsigned vs signed negatives

`structured_tool_body` MUST:

1. If the handler returned a Chirp `Envelope` or a wire dict with
   `signature` + `payload` → **`status: "ok"`** and pass `envelope_wire`.
   A sealed `{error: "run_not_found"}` (or any domain error) stays a
   **signed negative receipt**. Outer MCP status is ok because the tool
   produced a verifyable fact. Agents read `payload.error`.
2. If the handler returned an **unsigned** dict whose `error` value is a
   snake_case code → **`mcp_error_response(code, message)`**. Never wrap
   that as `status: "ok"`. No `envelope_wire`.
3. Otherwise → `status: "ok"` as today.

This completes ADR 0010 §5 for discovery tools without breaking managed
`run_not_found` inside a signed poll payload.

### 3. Stable codes; additive fields only

- Existing codes stay (`not_found`, `run_not_found`, `caller_not_allowed`,
  `publisher_direct_required`, `unknown_tool`, `invalid_arguments`,
  `call_failed`, `invalid_json`, `expected_object`, commerce ADR 0002
  `insufficient_balance`).
- New codes are allowed. **Renames and removals require an ADR bump.**
- HTTP may add `message` / `hint`. MCP may add `skill` / `tool`. Do not
  require clients to read new keys to detect failure.
- `call_failed.message` is a short stable phrase (`publisher call failed`),
  not `str(exc)`. Log the exception server-side.

### 4. Call-time admission

Managed `submit()` maps `RunAdmissionError` to a **structured dict**
`{error: <code>, ...}` at the tool boundary (signed if the star already
seals call-time rejects; otherwise unsigned MCP error). It MUST NOT
propagate `ManagedAdmissionRejected` through `/mcp` as an uncaught
exception.

### 5. Verify HTTP

`/api/envelope/verify` keeps `verified: bool`. On `verified: false` after
a well-formed object, add additive `error` (`invalid_signature`,
`unknown_key_id`, `malformed_wire`, `unsupported_alg`). Parse failures
stay `invalid_json` / `expected_object`. Commerce refund behavior is
unchanged.

### 6. Out of scope (do not “DRY” these)

- Per-star `skill.py` factories and env-var identity.
- `stars/signing.py` vs `stars/cpu_signing.py` namespaces.
- `dogfood.verify_receipt` (Envelope signature) vs bind-star
  `verify_receipt` (offline digest). Same name, different contracts.
- Canonical JSON key coercion across inventory stars — **separate
  design**; merging `_nfc_wire` vs `_nfc_normalize` changes digests.
- Satisfaction `status: "rejected"` vs MCP `status: "error"` — do not
  harmonize without a dual-trust design.
- Private-namespace auth on MCP discovery tools — wave:3 / security
  design; not this ADR’s first leaves.

## Consequences

- Leaves may assume unsigned `{error}` on `/mcp` is `status: "error"`.
- Leaves may not rename codes or collapse the three channels.
- Page UI may map codes to prose; JSON `error` / MCP `error.code` stay
  snake_case and grep-stable.
- A-tier grade for practices 1–3 is “agents parse one shape per
  boundary,” not “one shape for the whole repo.”
