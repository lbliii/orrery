# ADR 0009: AcceptanceReceipt (sealed sprint / done contract)

- **Status:** Accepted
- **Date:** 2026-08-11
- **Issues:** [#311](https://github.com/lbliii/orrery/issues/311),
  epic [#310](https://github.com/lbliii/orrery/issues/310),
  follow-on after saga [#237](https://github.com/lbliii/orrery/issues/237)
- **Depends on:** [0004](./0004-publisher-direct-call.md),
  [0005](./0005-discovery-and-dual-trust.md),
  [0006](./0006-decision-receipt.md) (complementary — not a rename),
  [0007](./0007-constellation-subtree-contract.md) (`acceptance_cites`)
- **Plan:** [tree-handling-rim.md](../plan/tree-handling-rim.md)

## Context

Harnesses that last across sessions seal **done criteria before code**
(Anthropic generator↔evaluator sprint contracts). Workers and constellations
need a citeable digest of those criteria — not another chat blob and not an
Orrery-hosted evaluator.

[ADR 0006](./0006-decision-receipt.md) freezes **policy / design** statements
(`DecisionReceipt`). Acceptance is a different speech act: “these checks mean
done.” Overloading DecisionReceipt would split-brain digests and blur planner
vs evaluator roles.

Orrery stays thin (ADR 0005): it **seals** criteria + verify refs; the harness
**runs** the evaluator and decides pass/fail.

## Decision

Adopt **option 2** from design [#311](https://github.com/lbliii/orrery/issues/311):
a distinct **AcceptanceReceipt** profile sealed by
`orrery/acceptance-bind`, citeable via a dedicated composite field.

### 1. AcceptanceReceipt profile

`orrery/acceptance-bind` accepts an acceptance id plus criteria; it returns a
signed Envelope whose **result** includes an AcceptanceReceipt:

| Field | Required | Meaning |
| --- | --- | --- |
| `acceptance_id` | yes | Caller-supplied stable id (ULID/UUID/string ≤128) |
| `criteria` | yes | Non-empty array of criterion objects (≤32) |
| `acceptance_digest` | yes | Lowercase hex `sha256` of canonical acceptance bytes |
| `sealed_at` | yes | UTC ISO-8601 from the star clock at seal time |
| `adr_url` | no | HTTPS URL pointing at an ADR (not hosted by Orrery) |
| `issue_url` | no | HTTPS URL pointing at a tracker issue |

### 2. Criterion object

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | Stable criterion id (kebab-case / slug; ≤64 chars) |
| `statement` | yes | Exact UTF-8 text of what must be true (≤4 KiB UTF-8) |
| `verify` | yes | VerifyRef object (below) |

Duplicate `id` values in one `criteria` array are rejected.

### 3. VerifyRef (machine pointer — not executed by Orrery)

| Field | Required | Meaning |
| --- | --- | --- |
| `kind` | yes | One of `pytest`, `command`, `http_smoke`, `envelope_verify`, `digest_eq`, `external_ref` |
| `ref` | yes | Machine string ≤1 KiB (pytest node id / CLI / URL / digest hex / opaque harness ref) |
| `expect` | no | Optional expected signal ≤1 KiB (e.g. exit `0`, HTTP `200`) |

v1 **does not** run `verify` refs inside the star. Sealing a contract is not
evaluating it. Harness / CI / constellation sensors own execution.

### 4. Canonical acceptance bytes

```text
canonical_acceptance_bytes(acceptance_id, criteria) =
  UTF-8 encoding of JSON object:
  {
    "acceptance_id": <NFC-normalized id>,
    "criteria": [ ... criteria sorted by id ascending ... ]
  }
  where each criterion is:
  {
    "id": <NFC>,
    "statement": <NFC>,
    "verify": {
      "kind": <exact enum string>,
      "ref": <NFC>,
      "expect": <NFC>   // omit key entirely when absent
    }
  }
  serialized with sort_keys=True, separators=(",", ":"), ensure_ascii=False
  (no BOM).
```

`acceptance_digest = sha256(canonical_acceptance_bytes).hexdigest()` (lowercase).

The star persists post-NFC `acceptance_id` and `criteria` in the receipt so
verify is offline.

### 5. Offline verify rules

1. Envelope signature verifies per
   [envelope-verification.md](../verification/envelope-verification.md).
2. Recompute `acceptance_digest` from persisted fields; require equality.
3. Reject empty `criteria`, unknown `verify.kind`, duplicate criterion ids, or
   oversized fields.
4. v1 does **not** require multi-party signatures.
5. Passing verify **does not** imply the harness ran the criteria successfully —
   only that the sealed contract bytes match the digest.

### 6. Composite cite field (do not overload `cites`)

Constellation composite receipts that depend on a sealed done-contract MUST
include:

```json
"acceptance_cites": ["<acceptance_digest>", "..."]
```

`acceptance_cites` is an array of lowercase hex `sha256` digests. It is
**parallel to** ADR 0006 `cites` (DecisionReceipt digests only). Do **not** put
acceptance digests in `cites`.

Citing a digest does **not** fetch criteria text from Orrery; the caller
retained the receipt or ADR. Missing `acceptance_cites` when a constellation
stage required an AcceptanceReceipt freeze is a constellation policy failure,
not an AcceptanceReceipt verify failure.

This extends ADR 0007 `composite_receipt_fields`: optional field
`acceptance_cites` with the semantics above. Protocol-star digests remain in
`chain`, not in `acceptance_cites`.

### 7. Non-goals

- Playwright / browser runner SKU
- Taste judges or LLM-as-evaluator products
- Orrery as ADR wiki or criteria host
- Executing `verify` refs inside `acceptance-bind`
- Extending DecisionReceipt with criteria (rejected option 1)
- Constellation-only stage field with no standalone seal (rejected option 3)

## Consequences

- Leaf implementing `orrery/acceptance-bind` cites this ADR for field names,
  digest rules, and VerifyRef kinds.
- Dogfood leaf adds `acceptance_cites` on one constellation composite receipt.
- Agent card for `acceptance-bind` should stamp `tree_role: planner` (informational;
  ADR 0005 still applies).
- Workers must not re-decide field names, digest canonicalization, or cite field
  naming.

## Examples (representable)

1. **Sprint leaf:** criteria =
   `[{id:"ruff", statement:"ruff check clean", verify:{kind:"command", ref:"uv run ruff check .", expect:"0"}},
     {id:"pytest-leaf", statement:"issue marker green", verify:{kind:"pytest", ref:"tests/stars/test_acceptance_bind.py"}}]`
2. **Constellation gate:** stage requires prior `acceptance_cites` entry before
   composite seal; harness supplies the digest from a sealed AcceptanceReceipt.
