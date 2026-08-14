# Design: Opt-in listing (newcomer shelf)

- **Status:** Accepted (planner freeze)
- **Date:** 2026-08-14
- **Binds:** [ADR 0012](../adr/0012-opt-in-listing.md)
- **Parent saga:** [#1](https://github.com/lbliii/orrery/issues/1)

## Question frozen

How do third-party publishers get a gaze/resolve row without Orrery hosting
them, crawling the web, or becoming a marketplace?

## Decision

Opt-in ping of one HTTPS listing file → `new/{slug}` row → agents call
publisher-direct → envelope-gated `rate_listing` → later promote on
distinct sealed `useful` evidence.

Listing ≠ marketplace (ADR 0001 carve-out). No isolate, no proxy-all, no
payouts, no essay reviews, no crawl.

## Listing file (`orrery-listing/0.1`)

JSON object (typically `/.well-known/orrery.json`):

| Field | Required | Notes |
| --- | --- | --- |
| `spec` | yes | `orrery-listing/0.1` |
| `name` | yes | Desired Skill DNS name (`publisher/invoice-check`) |
| `summary` | yes | ≤280 chars |
| `use_when` | yes | 1–3 bullets |
| `endpoint` | yes | HTTPS MCP URL |
| `transport` | yes | `streamable-http` |
| `tools` | yes | 1–24 names only (no schemas) |
| `price_per_call` | no | |
| `key_id` | no | |
| `alg` | no | default `Ed25519` |
| `contact` | no | |
| `inputs_summary` | no | |

Reserved prefixes cannot be claimed (`orrery`, `public`, `mcp`, `new`, …).
Until promotion the live row is `new/{slug}`. Listing URL host and
`endpoint` host must share a registrable domain (fixture kind skips this).

Fetch: HTTPS only; no redirects; block private / link-local / metadata
IPs; 64 KiB; timeout. We never fetch a host we were not told about.

## Catalog row

- `kind=star`, `visibility=public`, `name=new/{slug}`
- `endpoint` = their HTTPS URL
- `oracle_ok=false`, `index_tier=newcomer`
- `content_digest` = `sha256:` + hex of listing bytes
- Agent card built from the file; **not** in `AGENT_CARDS` CI
- `/stars` human catalog stays first-party (no `index_tier`)
- Empty-intent public gaze sorts newcomers after first-party rows

## Crowdsourced vetting

Reuse `useful | stale | broken | wrong-price`. Gaze/describe on `new/`
hits hint: after you seal, `rate_listing`. Slim `/mcp` lists `index_ping`
and `rate_listing`. `rate` / `star_rate` stay on `/mcp/dogfood`.
Registration stays `{"dynamic": false}`.

## Promotion rule

Promote `new/{slug}` → claimed `name` when all hold on the live digest:

- ≥ 100 sealed (`envelope_id`) ratings with verdict `useful`
- ≥ 10 distinct `caller_namespace` values among those
- `broken` / `wrong-price` share of sealed ratings ≤ 25%

Keep `new/` as an alias with `promoted_to`. Demotion is later.

## What leaves may assume

- `listings/` owns parse, SSRF fetch, fixture allowlist, in-process store,
  record projection, ping, and promotion helpers.
- `refresh_catalog` merges `listing_records()`.
- `required_public_card_names()` stays builtin-only.
- `new` is a reserved namespace slug.
- Slim `/mcp` lists `index_ping` and `rate_listing` (ten tools total).
- Desired public names must not use the `acme/` demo tenant.
