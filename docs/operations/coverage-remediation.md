# Coverage remediation on deny (#340)

When `coverage_check` or `GET /coverage/{star}/check` rejects a value
(`reason=not_allowlisted`), the response is additive:

- `allowed_values` — non-empty sample of valid entries for that star
- `catalog_href` — path to the live `/coverage/{star}` catalog page

Constellations listed in coverage **gaps** (no named SKU map on the composer)
return `kind=coverage_gap` from `GET /coverage/{star}` with
`upstream_allowlists` pointing at member stars that publish allowlists
(e.g. `table-fresh` → `csv-url`).

Preflight before calling allowlist-gated stars; do not expand membership via
coverage — it documents existing public entries only.
