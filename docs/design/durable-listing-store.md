# Design: Durable listing + satisfaction store

- **Status:** Accepted (planner freeze)
- **Date:** 2026-08-14
- **Design issue:** [#453](https://github.com/lbliii/orrery/issues/453)
- **Parent epic:** [#452](https://github.com/lbliii/orrery/issues/452)
- **Binds:** [ADR 0012](../adr/0012-opt-in-listing.md),
  [opt-in-listing.md](./opt-in-listing.md),
  [satisfaction-schema.md](./satisfaction-schema.md)

## Question frozen

Where do listing rows and envelope-gated ratings live across process
restart, and what may a promote / demote job assume?

## Decision

Postgres behind the existing protocols. Same `DATABASE_URL` the host
already uses for artifacts and constellation runs. No new engine.

In-memory stubs stay for unit tests. The Postgres adapters fail closed
if constructed without `DATABASE_URL` (artifact pattern). Host factories
select Postgres when the URL is set; tests keep injecting in-memory.

No new ADR unless this repo contract outlives #452 in a way 0012 does
not already cover.

## Listings table

Name: `listing_rows`. Unique key is the submitted `listing_url`.

| Column | Type | Notes |
| --- | --- | --- |
| `listing_url` | TEXT PK | HTTPS URL we were told to fetch |
| `listing_json` | JSONB NOT NULL | Last successful listing document |
| `content_digest` | TEXT NOT NULL | Live digest (`sha256:` + hex) |
| `live_name` | TEXT NOT NULL | `new/{slug}` |
| `claimed_name` | TEXT | Desired Skill DNS name |
| `endpoint` | TEXT NOT NULL | Publisher HTTPS MCP URL |
| `index_tier` | TEXT NOT NULL | `newcomer` \| `registered` |
| `promoted_to` | TEXT | Claimed name after promotion |
| `quiet` | BOOLEAN NOT NULL DEFAULT FALSE | Hidden from public shortlist |
| `last_fetch_at` | TIMESTAMPTZ | Last successful or failed fetch |
| `last_error` | TEXT | Last fetch / parse code, or null |
| `created_at` | TIMESTAMPTZ NOT NULL | |
| `updated_at` | TIMESTAMPTZ NOT NULL | |

Ping upserts by `listing_url`. Boot loads durable rows, projects each
via existing `listing_to_record`, then merges `listings/allowlist.json`
fixtures (fixture `fixture://` URLs cannot collide with HTTPS pings).

A refetch job iterates **known `listing_url`s only**. It never discovers
hosts.

## Satisfaction table

Name: `satisfaction_ratings`. Record shape is already frozen — do not
invent columns or verdicts.

| Column | Type | Notes |
| --- | --- | --- |
| `content_digest` | TEXT | |
| `authority_id` | TEXT | `envelope_id` or `call_attempt_id` |
| `authority_kind` | TEXT | `envelope` \| `call_attempt` |
| `star_name` | TEXT NOT NULL | |
| `verdict` | TEXT NOT NULL | `useful` \| `stale` \| `broken` \| `wrong-price` |
| `note` | TEXT | ≤280 |
| `caller_namespace` | TEXT | |
| `created_at` | TIMESTAMPTZ NOT NULL | |

Primary key: `(content_digest, authority_id)`.

Aggregates stay `(star_name, content_digest)`. Digest change ⇒ live
pill and promotion reset (existing rule). Historical rows stay.

`SatisfactionStore` / `get_satisfaction_store()` grow a durable adapter.
Call sites do not change.

## Quiet, not a new visibility

Pick **`quiet` on the listing row**, not a new `ResolveRecord.visibility`
value and not a new `untrustworthy` verdict.

- Quiet rows stay in the catalog so `resolve_name` still works.
- Public empty-intent gaze drops names in `listings.store.quiet_names()`.
- Do not tattoo the claimed name across digest changes: a new live
  digest clears `quiet` and `promoted_to` on that row.

## Demotion rule (live digest only)

On the **live** digest, if the sealed (`envelope_id`) share of
`broken` + `wrong-price` exceeds **25%** (same ceiling as ADR 0012
promotion), set `quiet=true`.

Promotion thresholds stay as frozen in opt-in-listing.md. The job
applies both rules with injectable thresholds in tests.

## Job

`listings.job.refetch_known()` is deterministic and testable. Periodic
vs on-rate hook is an implementation detail of the job leaf. Not a
publisher console. Not a crawl.

## Factory / fail-closed

- Tests: inject `InMemory` stores (today's default).
- `DATABASE_URL` set: Postgres adapters; `CREATE TABLE IF NOT EXISTS`
  on first initialize (same style as `artifacts.domain`).
- Postgres adapter constructed without a URL: raise a typed
  configuration error. Do not silently write memory and call it durable.
- Deployed `index_ping` / `rate_listing`: if `DATABASE_URL` is unset,
  return a parseable `store_unavailable` error (ADR 0010 / 0011). Do
  not pretend the row survives restart.

## What leaves may assume

- `listings.store` and `trust.satisfaction.get_satisfaction_store()`
  grow durable adapters; ping / rate / pill / `apply_promotion` call
  sites keep their current function signatures.
- Workers do not invent columns, a second rating product, or a crawl.
- Homepage copy leaf (#454) does not wait on this design.
- No new ADR in these leaves.

## Non-goals

- Publisher analytics console
- Free-text reviews, reputation graphs, paid rank
- Crawling any host we were not given
- `untrustworthy` verdict
- New database engine / sidecar
