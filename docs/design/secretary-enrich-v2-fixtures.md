# Design: Secretary enrich stars (v2 fixture providers)

- **Status:** Accepted (planner freeze — extends v1)
- **Date:** 2026-08-11
- **Parent epic:** [#83](https://github.com/lbliii/orrery/issues/83)
- **Extends:** [secretary-enrich-v1.md](./secretary-enrich-v1.md)
- **Related spike:** [#139](https://github.com/lbliii/orrery/issues/139) (live Maps — stays open)

## Question frozen

May remaining enrich stars ship as **fixture / named-target allowlist** SKUs
(like `http-head` / `tz-resolve`) without waiting on a live Google Maps or
airline contract?

## Decision

Yes. Specimen sky needs clear SKUs first. Live Maps (#139) remains a separate
experimental spike and must not block fixture stars.

| Star | SKU | Provider rule (v2 fixture) |
| --- | --- | --- |
| `orrery/geocode` | allowlisted place token → lat/lon + display name | Offline fixture table only; unknown token fails loud; no Maps API |
| `orrery/place-hours` | allowlisted venue token → hours / open-now | Offline fixture table; `as_of` optional; no Places API |
| `orrery/flight-status` | allowlisted flight id + date → status fields | Offline fixture schedule/status; no live airline egress in v2 |

All three: `allowed_egress = []` (or empty), non-empty `CORPUS`, L0 negatives,
Envelope seal. Attribution field may say `provider: "orrery-fixtures"`.

### Still out of scope / later

- Live Google Maps key path (#139)
- Live flight provider egress
- `orrery/invite-ready` (#110) until member stars exist (tz + holidays already
  shipped; wait for these three or redefine graph to available members in a
  follow-on freeze)

## What leaves may assume

- [#105](https://github.com/lbliii/orrery/issues/105),
  [#106](https://github.com/lbliii/orrery/issues/106),
  [#109](https://github.com/lbliii/orrery/issues/109) implement against this
  table without inventing live providers.
- Do not close #139; do not proxy Maps content into receipts.
