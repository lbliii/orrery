# ADR 0012: Opt-in listing (newcomer shelf)

- **Status:** Accepted
- **Date:** 2026-08-14
- **Parent saga:** [#1](https://github.com/lbliii/orrery/issues/1)
- **Depends on:** [0001](./0001-control-plane-wallet.md),
  [0004](./0004-publisher-direct-call.md),
  [0005](./0005-discovery-and-dual-trust.md),
  [0010](./0010-aggregate-mcp-call-skill.md)
- **Design:** [opt-in-listing.md](../design/opt-in-listing.md)

## Context

The public catalog is first-party packages synced at boot. ADR 0004 already
says a third-party star only needs a resolvable endpoint + Envelope signing,
but there is no ingest path. ADR 0001 still forbids an **untrusted
marketplace + isolate sandbox**. Agents need a way to opt in — ping a file
we were told about, land in a newcomer namespace, and let other agents score
them — without Orrery crawling the web or proxying their tools.

## Decisions

### 1. Listing ≠ marketplace (ADR 0001 carve-out)

Opt-in **metadata listing** is in scope. Isolate sandbox, proxy-all-calls,
payouts, paid promotion, Yelp essays, and crawling any host we were not
given stay Not now. Anyone may be *found* under `new/`. A stable claimed
name requires sealed evidence.

### 2. Intake is opt-in fetch, never crawl

Submit one HTTPS URL via `POST /api/listings/ping` or MCP `index_ping`.
Orrery fetches **that URL only**. A checked-in allowlist may load fixture
files at boot (no network).

### 3. Listing file (`orrery-listing/0.1`)

JSON object (typically `/.well-known/orrery.json`): `spec`, `name`
(desired Skill DNS name), `summary`, `use_when` (1-3), `endpoint` (https),
`transport` (`streamable-http`), `tools` (names only); optional
`price_per_call`, `key_id`, `alg`, `contact`, `inputs_summary`.

Reserved prefixes cannot be claimed. Until promotion the live row is
`new/{slug}`. Listing URL host and `endpoint` host must share a
registrable domain (fixture kind skips this).

Fetch: HTTPS only; no redirects; block private / link-local / metadata
IPs; 64 KiB; timeout.

### 4. Catalog row

`kind=star`, `visibility=public`, `name=new/{slug}`, publisher HTTPS
endpoint, `oracle_ok=false`, `index_tier=newcomer`, `content_digest` =
sha256 of listing bytes. Agent card is built from the file and is **not**
required in `AGENT_CARDS` CI. `call_skill` remains
`publisher_direct_required`. `/stars` human catalog stays first-party
(no `index_tier`).

### 5. Crowdsourced vetting (no Yelp)

Reuse `useful | stale | broken | wrong-price`. Gaze/describe on `new/`
hits hint: after you seal, `rate_listing`. Slim `/mcp` grows `index_ping`
and `rate_listing`. `rate` / `star_rate` stay on `/mcp/dogfood`.

### 6. Promotion rule

Promote `new/{slug}` → claimed `name` when all hold on the live digest:

- ≥ 100 sealed (`envelope_id`) ratings with verdict `useful`
- ≥ 10 distinct `caller_namespace` values among those
- `broken` / `wrong-price` share of sealed ratings ≤ 25%

## Consequences

- Implementers cite this ADR + [opt-in-listing.md](../design/opt-in-listing.md).
- Advertised `/mcp` is the ADR 0010 set plus `index_ping` and `rate_listing`.
