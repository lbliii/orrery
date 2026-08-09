# Plan: Specimen sky — sample the pattern library

- **Status:** Draft — saga [#76](https://github.com/lbliii/orrery/issues/76)
- **Date:** 2026-08-09
- **Parent product saga:** [#1](https://github.com/lbliii/orrery/issues/1)
- **Strategy saga:** [#56](https://github.com/lbliii/orrery/issues/56) (vending-machine sky / discovery / dual trust)
- **Conventions:** [scouting.md](../design/scouting.md) · [atlas.md](../design/atlas.md)
- **Depends on:** [ADR 0001](../adr/0001-control-plane-wallet.md), [ADR 0004](../adr/0004-publisher-direct-call.md), [ADR 0005](../adr/0005-discovery-and-dual-trust.md)

## Why this matters

Orrery’s shared-value thesis is clearest when the **public sky samples every
callable shape** across a few industries — not when it ships thirty variants of
one fetch. A specimen tranche teaches scouts to ask *“is this rim?”* instead of
*“how do we thicken the harness?”*

Without a curated sample:

1. We overbuild one vertical (docs-only) and look like a niche crawler.
2. We under-teach freshen / slice / diff / validate / join / transform / attest.
3. Products like Pidge have nothing concrete to recommend in their agent atlases.
4. The economic pitch (“buy a fact vs explore”) stays abstract.

**Fix:** Ship ~22 public stars + 4 story constellations that maximize **pattern
coverage**, then use that sky as the scouting template for later waves.

## Through line

Sticky software keeps the **system of record**. Harnesses keep trying to own
every power. Orrery takes the **agent-facing rim** — freshen · slice · diff ·
validate · join · enrich · transform · attest — and makes it named,
digest-keyed, payable, and pointed. Apps ship **maps to stars**; publishers run
compute; agents keep judgment.

Sharpened line: *Maximum pattern coverage, not thirty fetch clones.*

## GitHub issue map

| Sprint | Epic | Tasks |
| --- | --- | --- |
| S0 | [#77](https://github.com/lbliii/orrery/issues/77) Specimen conventions | [#85](https://github.com/lbliii/orrery/issues/85) litmus + shapes · [#86](https://github.com/lbliii/orrery/issues/86) atlas |
| S1 | [#78](https://github.com/lbliii/orrery/issues/78) Parable + stale-proof | [#87](https://github.com/lbliii/orrery/issues/87)–[#88](https://github.com/lbliii/orrery/issues/88) |
| S2 | [#79](https://github.com/lbliii/orrery/issues/79) Web truth · [#80](https://github.com/lbliii/orrery/issues/80) Docs-as-data | [#89](https://github.com/lbliii/orrery/issues/89)–[#94](https://github.com/lbliii/orrery/issues/94) |
| S3 | [#81](https://github.com/lbliii/orrery/issues/81) Tabular + table-fresh | [#95](https://github.com/lbliii/orrery/issues/95)–[#99](https://github.com/lbliii/orrery/issues/99) |
| S4 | [#82](https://github.com/lbliii/orrery/issues/82) Supply chain + ship-check | [#100](https://github.com/lbliii/orrery/issues/100)–[#104](https://github.com/lbliii/orrery/issues/104) |
| S5 | [#83](https://github.com/lbliii/orrery/issues/83) Secretary + invite-ready | [#105](https://github.com/lbliii/orrery/issues/105)–[#110](https://github.com/lbliii/orrery/issues/110) |
| S6 | [#84](https://github.com/lbliii/orrery/issues/84) Money-light (P3) | [#111](https://github.com/lbliii/orrery/issues/111)–[#112](https://github.com/lbliii/orrery/issues/112) |

Saga: [#76](https://github.com/lbliii/orrery/issues/76). Litmus + shapes:
[scouting.md](../design/scouting.md). Product atlases: [atlas.md](../design/atlas.md).

## Litmus + shapes (summary)

Full checklist and hard-no list live in [scouting.md](../design/scouting.md).

Ship a public star only if most litmus tests pass (stale-if-cloned, clear SKU,
allowlistable, receipt useful, shared, not hands/SoR, harnesses fake as magic).

Shapes to sample: **freshen · slice · diff · validate · join · enrich ·
transform · attest · gate**.

## Specimen portfolio

### Stars (~22)

| Cohort | Stars | Shapes sampled |
| --- | --- | --- |
| **A Parable** | world-time, source-watch, html-to-pdf | freshen, diff, transform + attest |
| **B Web truth** | http-head, well-known, cert-expiry | freshen, slice |
| **C Docs-as-data** | rfc-section, pep-section, spdx-license | slice |
| **D Tabular rim** | csv-url, table-diff, row-lookup, row-validate | freshen, diff, slice, validate |
| **E Supply chain** | pypi-release, npm-release, gh-file-at-ref, gh-release-notes | freshen, slice, diff |
| **F Secretary enrich** | flight-status, geocode, tz-resolve, holidays, place-hours | freshen, enrich |
| **G Money-light** | fx-rate, tax-region | freshen, validate |

### Constellations (4)

| Name | Graph | Story |
| --- | --- | --- |
| `orrery/stale-proof` | time + source-watch (+ optional pdf) | Clone fails; buy truth |
| `orrery/ship-check` | pypi/npm + source-watch + time | CI without harness bloat |
| `orrery/table-fresh` | csv-url + table-diff | Spreadsheet rim |
| `orrery/invite-ready` | time + flight + geocode/hours | Pidge atlas bait |

## Invariants

1. Allowlisted sources only — no open-web proxy star.
2. Gaze stays payload-free; live body only on call + Envelope.
3. Publisher-direct call path (ADR 0004); dogfood on this host is demo.
4. Each star teaches a shape; avoid duplicate “fetch URL” clones.
5. Products recommend SKUs; they do not hard-depend on a single publisher forever.

## Sprint overview

| Sprint | Focus | Effort | Risk | Ships independently? |
| --- | --- | --- | --- | --- |
| **0** | Conventions: litmus, shapes, atlas | 4h | Low | Yes (docs) |
| **1** | Parable brand + `stale-proof` | 8–12h | Low | Yes |
| **2** | Web truth + docs-as-data | 16–24h | Medium | Yes |
| **3** | Tabular rim + `table-fresh` | 16–24h | Medium | Yes |
| **4** | Supply chain + `ship-check` | 16–24h | Medium | Yes |
| **5** | Secretary enrich + `invite-ready` | 20–30h | Medium | Yes |
| **6** | Money-light (optional) | 8–12h | Low | Yes |

Do not block saga #1 Wave 0/1 pointing loop — specimen stars ride Wave 1+
reactive pattern.

## Relationship to existing work

- **#1** — Product north star; specimen sky is Wave 1+ content, not a new control plane.
- **#56** — Discovery/dual-trust strategy; specimen sky is the **content** that strategy serves.
- **#8** — Constellations epic; story constellations are dogfood under that model.
- **Existing stars** — world-time, source-watch, html-to-pdf are cohort A (brand + compose, don’t rebuild).

## Not now

- Review authenticity / product ranking marketplaces
- Full Sheets / Airtable / GitHub / Gmail clones
- Open-ended travel planner
- Local filesystem / shell as public stars
- Untrusted third-party isolate sandbox (ADR 0001)

## Next action

1. Close Sprint 0 conventions (#77 / #85 / #86) via [scouting.md](../design/scouting.md) + [atlas.md](../design/atlas.md).
2. Sprint 1: brand parable cohort + `orrery/stale-proof` (#78).
