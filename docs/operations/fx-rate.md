# FX rate allowlist

`orrery/fx-rate` returns a pinned **foreign-exchange rate** for an allowlisted
**currency pair token** and **as-of calendar date** using an offline fixture
table only. There is no live market feed, Stripe integration, wallet ledger,
or checkout path.

Initial pair tokens: `usd-eur`, `usd-gbp`, `usd-jpy`, `eur-gbp`, `gbp-jpy`, and
`eur-usd`. Pinned as-of dates: `2026-01-15`, `2026-06-01`, and `2026-08-01`.
Requests for unknown pair tokens fail with `pair_not_allowed`. Dates outside the
pinned revision fail with `as_of_not_available`. The star is a join/enrich shape
for quotes — not a payments platform (see wallet ADRs).

Attribution on successful calls uses `provider: "orrery-fixtures"`.
