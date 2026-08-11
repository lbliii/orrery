# Public holidays allowlist

`orrery/holidays` returns a pinned public-holiday list for an **allowlisted
ISO 3166-1 alpha-2 region code** and **pinned calendar year**. The dataset is
static and offline — there is no crawl, geocoder, or live holiday provider.

Initial region codes: `US`, `GB`, `JP`, `AU`, `FR`, `DE`, and `CA`. Pinned
years: `2025`, `2026`, and `2027`. Requests for unknown region codes fail with
`region_not_allowed`. Years outside the pinned revision fail with
`year_not_available`. The star is not a trip planner.
