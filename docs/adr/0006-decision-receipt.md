# ADR 0006: DecisionReceipt (citeable planner freeze)

- **Status:** Accepted
- **Date:** 2026-08-10
- **Issues:** [#242](https://github.com/lbliii/orrery/issues/242),
  epic [#239](https://github.com/lbliii/orrery/issues/239),
  saga [#237](https://github.com/lbliii/orrery/issues/237)
- **Depends on:** [0004](./0004-publisher-direct-call.md),
  [0005](./0005-discovery-and-dual-trust.md)
- **Plan:** [tree-handling-rim.md](../plan/tree-handling-rim.md)

## Context

Agent swarms split-brain when two planners decide the same question differently.
Merge tooling cannot fix two pictures of reality. The scarce fix is a **citeable
freeze**: a bounded statement whose digest downstream work can reference.

Orrery must not host full ADRs or mediate debate (thin harness). It can seal a
small DecisionReceipt so workers and constellations cite a digest the way they
cite any other Envelope evidence.

## Decision

### 1. DecisionReceipt profile (not free-form Envelope JSON alone)

`orrery/decision-bind` accepts a decision statement and optional links; it
returns a signed Envelope whose **result** includes a DecisionReceipt:

| Field | Required | Meaning |
| --- | --- | --- |
| `decision_id` | yes | Caller-supplied stable id (ULID/UUID/string ≤128) |
| `statement` | yes | Exact UTF-8 decision text the digest binds |
| `decision_digest` | yes | `sha256` hex of **canonical statement bytes** (below) |
| `decided_at` | yes | UTC ISO-8601 from the star clock at seal time |
| `adr_url` | no | HTTPS URL pointing at an ADR (not hosted by Orrery) |
| `issue_url` | no | HTTPS URL pointing at a tracker issue |

Verify rules:

1. Envelope signature verifies per
   [envelope-verification.md](../verification/envelope-verification.md).
2. Recompute `sha256(canonical_statement_bytes(statement))` and require equality
   with `decision_digest`.
3. Reject if `statement` is empty or >16 KiB UTF-8.
4. v1 does **not** require multi-party signatures.

### 2. Canonical statement bytes

```text
canonical_statement_bytes(statement) =
  UTF-8 encoding of statement with NFC normalization,
  no BOM, and no trailing newline stripping beyond what the caller sent
  (digest binds exact caller string after NFC only).
```

The star persists the post-NFC `statement` in the receipt so verify is offline.

### 3. Composite cite field

Constellation composite receipts that depend on a freeze MUST include:

```json
"cites": ["<decision_digest>", "..."]
```

`cites` is an array of lowercase hex `sha256` digests. Citing a digest does
**not** fetch statement text from Orrery; the caller retained the statement or
ADR. Missing cite when a constellation stage required a freeze is a constellation
policy failure, not a DecisionReceipt verify failure.

### 4. Non-goals

- Orrery as ADR wiki or design-doc host
- Multi-party voting / quorum signatures in v1
- Orrery mediating planner debate or merge conflicts
- Embedding full issue/ADR bodies in the Envelope

## Consequences

- Leaf [#244](https://github.com/lbliii/orrery/issues/244) implements
  `orrery/decision-bind` against this contract.
- Leaf [#245](https://github.com/lbliii/orrery/issues/245) dogfoods a `cites`
  entry on one constellation composite receipt.
- Design [#242](https://github.com/lbliii/orrery/issues/242) is closed by this
  ADR; workers must not re-decide field names or digest rules.

## Examples (representable)

1. **Constellation policy:** “pause for typed decision on unsupported MyST
   directive; do not invent MDX.”
2. **Allowlist change:** “add `https://peps.python.org/peps.json` to
   `source-watch` allowlist target set v3.”
