# Design: Satisfaction schema (digest + envelope-gated)

- **Status:** Accepted (planner freeze)
- **Date:** 2026-08-11
- **Design issue:** [#67](https://github.com/lbliii/orrery/issues/67)
- **Parent epic:** [#59](https://github.com/lbliii/orrery/issues/59)
- **Binds:** [ADR 0005](../adr/0005-discovery-and-dual-trust.md) §3 dual trust

## Question frozen

What record shape and stub-store interface may demand-side satisfaction
leaves (`rate`, aggregate pills) assume without inventing a review product?

## Decision

### 1. Rating record (v1)

| Field | Required | Notes |
| --- | --- | --- |
| `star_name` | yes | Canonical resolve name (e.g. `orrery/world-time`) |
| `content_digest` | yes | Skill/content digest at call time (lowercase hex `sha256`) |
| `envelope_id` | yes* | Call receipt id; *or* `call_attempt_id` when the call failed before seal |
| `call_attempt_id` | yes* | Failed-call token; mutually exclusive with successful `envelope_id` |
| `verdict` | yes | Exactly one of `useful` \| `stale` \| `broken` \| `wrong-price` |
| `note` | no | Optional one-liner; max 280 chars; no essay marketplace |
| `caller_namespace` | no | Tenant/namespace of the rating caller when known |
| `created_at` | yes | ISO-8601 UTC timestamp |

Authority: a guessable name is not enough — store writes require a prior
Envelope id or documented failed-call token (ADR 0005).

### 2. Store keying

Primary key for upsert / uniqueness:

```text
(content_digest, envelope_id | call_attempt_id)
```

`star_name` alone is **insufficient**. Aggregates group by
`(star_name, content_digest)` then by `verdict`.

### 3. Digest change → decay / reset

When the live resolve digest for `star_name` ≠ a rating's `content_digest`:

- That rating **does not** count toward the live aggregate pill.
- Historical ratings remain queryable for the old digest (no silent rewrite).
- Live pill is quiet/empty when no ratings match the current digest.

No automatic rewrite of old verdicts onto a new digest.

### 4. Stub store interface (leaves must implement against this)

```python
class SatisfactionStore(Protocol):
    def put(self, record: SatisfactionRecord) -> SatisfactionRecord: ...
    def get_for_receipt(
        self, *, content_digest: str, envelope_id: str | None,
        call_attempt_id: str | None,
    ) -> SatisfactionRecord | None: ...
    def aggregate(
        self, *, star_name: str, content_digest: str, since: datetime | None = None,
    ) -> SatisfactionAggregate: ...
```

`SatisfactionAggregate` (v1): counts per verdict, `total`, optional
`window` (e.g. `7d`). Empty aggregate ⇒ quiet UI (no fake scores).

In-memory stub is acceptable for #68/#69; durable SQL can follow without
changing the record shape.

### 5. Non-goals

- Free-text review marketplace / social feed
- Debit or wallet mutation inside `rate` (ADR 0001–0003)
- Route-accept ceremony (“did you like the gaze pick?”)
- Using satisfaction as a payment signal

## What leaves may assume

- [#68](https://github.com/lbliii/orrery/issues/68) implements MCP `rate` /
  `star_rate` against this store; rejects missing receipt.
- [#69](https://github.com/lbliii/orrery/issues/69) projects compact aggregate
  pills on gaze / resolve / star; quiet when empty or digest-mismatched.
- [#120](https://github.com/lbliii/orrery/issues/120) may cite this schema for
  eval/health narrative after #69 lands.

## ADR

No new ADR — vocabulary already in ADR 0005 §3; this note freezes the store
shape and decay policy.
