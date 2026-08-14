# Opt-in publisher index (newcomer shelf)

Publishers (or another agent pointing at their file) submit one HTTPS
`orrery-listing/0.1` URL. Orrery fetches **that URL only**, validates it,
and lands a public row at `new/{slug}` with `index_tier=newcomer` and
`oracle_ok=false`. Agents resolve the publisher endpoint, call it directly,
then `rate_listing` after they seal. See [ADR 0012](../adr/0012-opt-in-listing.md)
and [opt-in-listing.md](../design/opt-in-listing.md).

## Intake

- MCP: `index_ping` with `{ "url": "https://…/orrery.json" }`
- HTTP: `POST /api/listings/ping` with the same JSON (CSRF-exempt)
- Durable bootstrap: `listings/allowlist.json` `kind: fixture` files (no network)

We never fetch a host that was not submitted. HTTPS only; no redirects;
private / link-local / metadata IPs blocked; 64 KiB; timeout.

## After you seal, rate

`rate_listing` verdicts: `useful | stale | broken | wrong-price`.
Optional 280-character note. Envelope-gated. No essay reviews.
`rate` / `star_rate` stay on `/mcp/dogfood`.

Off-origin `call_skill` still returns `publisher_direct_required`.

## Promotion (follow-on)

`new/{slug}` → claimed name when the live digest has ≥100 sealed `useful`
ratings from ≥10 distinct `caller_namespace`s and ≤25% `broken` /
`wrong-price`. Thresholds are injectable in tests.

## Verify

```bash
uv run pytest tests/test_listings.py tests/test_discovery.py tests/test_app.py -q
uv run ruff check .
```
