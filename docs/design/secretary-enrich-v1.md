# Design: Secretary enrich stars (v1 slice)

- **Status:** Accepted (planner freeze — partial epic #83)
- **Date:** 2026-08-11
- **Parent epic:** [#83](https://github.com/lbliii/orrery/issues/83)
- **Parent saga:** [#76](https://github.com/lbliii/orrery/issues/76)
- **Binds:** [scouting.md](./scouting.md) enrich shape; ADR 0005 allowlistable SKUs

## Question frozen

Which secretary-enrich stars may ship first without inventing an open-web
browser or unpaid Maps/Flight provider contract?

## Decision

### Ready now (offline / deterministic allowlist)

| Star | SKU | Provider rule (v1) |
| --- | --- | --- |
| `orrery/tz-resolve` | latlon or named place token → IANA timezone | Offline table / library only; named place tokens must be **allowlisted fixtures** (no arbitrary geocoding inside this star) |
| `orrery/holidays` | region/country code + year → holiday list | Static dataset or pinned library; region codes allowlisted; no crawl |

Both must ship `star.toml` + contract/service/skill + non-empty `CORPUS` + L0
negatives (out-of-allowlist fails loud) + Envelope seal.

### Still blocked (need provider freeze)

| Star | Why |
| --- | --- |
| `orrery/geocode` | Needs attributable geocoder (#139 / Maps) |
| `orrery/flight-status` | Needs airline/status provider allowlist + live egress policy |
| `orrery/place-hours` | Needs place/hours provider |
| `orrery/invite-ready` | Constellation (#110) — blocked until member stars exist |

### Non-goals (all enrich stars)

- Open-ended trip / restaurant planners
- Arbitrary URL fetch
- Bundling judgment UX (Pidge atlas copy may *recommend* SKUs; stars stay rim facts)

## What leaves may assume

- [#107](https://github.com/lbliii/orrery/issues/107) / [#108](https://github.com/lbliii/orrery/issues/108)
  implement against this table without re-deciding provider shape.
- Follow world-time / http-head patterns for allowlist + corpus.
- Epic #83 stays open until all five stars + invite-ready exit.
