# Star scouting — litmus + shape library

- **Status:** Draft (convention freeze) — epic [#77](https://github.com/lbliii/orrery/issues/77)
- **Date:** 2026-08-09
- **Parent saga:** [#76](https://github.com/lbliii/orrery/issues/76) Specimen sky
- **Plan:** [specimen-sky.md](../plan/specimen-sky.md)
- **Related:** [ADR 0005](../adr/0005-discovery-and-dual-trust.md), [atlas.md](./atlas.md)

How to decide what belongs in the public sky. Short. Instrument-manual.

## Through line

Sticky software keeps the **system of record**. Harnesses keep trying to own
every power. Orrery takes the **agent-facing rim** — freshen · slice · diff ·
validate · join · enrich · transform · attest — and makes it named,
digest-keyed, payable, and pointed.

Apps (e.g. Pidge) ship **maps to stars**. Publishers run compute. Agents keep
judgment. See [atlas.md](./atlas.md).

## The lens

For any sticky base, draw three layers — only mine the middle:

```text
┌─────────────────────────────────────┐
│  SYSTEM OF RECORD (sticky UX)       │  Sheets, airline site, Gmail, GitHub
├─────────────────────────────────────┤
│  AGENT-FACING RIM (callables)       │  freshen · slice · validate · join · attest
├─────────────────────────────────────┤
│  LOCAL HANDS / PRODUCT VERBS        │  my files, my loft mail, my checkout UI
└─────────────────────────────────────┘
```

Orrery only wants the **rim** — named, digest-keyed, sealed callables. Not the
record. Not the hands.

**Rule of thumb:** if the hard part is *judgment over the whole world*, it is a
harness/assistant. If the hard part is *getting a fresh, attributable fact or
sealed transform*, it is a star.

## Litmus checklist

Ship it as a public star only if **most** are true:

| # | Test | Pass means |
| --- | --- | --- |
| 1 | **Stale-if-cloned?** | Offline copy loses the value |
| 2 | **Clear SKU?** | Identity in → bounded result out |
| 3 | **Allowlistable?** | Not “browse the open web” |
| 4 | **Receipt useful?** | Someone would keep an Envelope |
| 5 | **Shared?** | Many agents/products would call it |
| 6 | **Not hands / not SoR?** | Not filesystem, not full Sheets/Gmail/checkout |
| 7 | **Harnesses fake this as magic today?** | Cultural walk-back opportunity |

Ask once more: *Would Pidge (or CI, or a docs agent) recommend this SKU in a
one-liner?* If yes, it is ecosystem bait.

## Shape library

Map every candidate rim step to a shape. Prefer teaching **one shape well**
over shipping thirty fetch clones.

| Shape | Verb | What it returns | Specimen examples |
| --- | --- | --- | --- |
| **Freshen** | observe / get-as-of | Live reading + as-of + digest | `world-time`, `flight-status`, `http-head`, `pypi-release` |
| **Slice** | get(id, section/range) | Addressable fragment | `rfc-section`, `pep-section`, `row-lookup`, `gh-file-at-ref` |
| **Diff** | compare digests | Bounded change summary | `source-watch`, `table-diff` |
| **Validate** | check against schema/policy | Pass/fail + reasons | `row-validate`, `tax-region` |
| **Join** | lookup + merge keyed facts | Enriched record | FX + SKU, flight + tz |
| **Enrich** | add shared context | Extra fields from a publisher | `geocode`, `tz-resolve`, `holidays`, `place-hours` |
| **Transform** | pure faucet | Derived artifact + digest | `html-to-pdf` |
| **Attest** | seal / verify | Envelope identity | Any of the above on verify |
| **Gate** | tiny constellation (2–4 stars) | Composite receipt | `stale-proof`, `ship-check`, `table-fresh`, `invite-ready` |

Compose 2–4 stars into a **gate** constellation when the story is “only proceed
if truth holds.” Leave open-ended planning to the agent.

## Scouting process

1. Pick a sticky base (Sheets, Git, Gmail, airline, docs…).
2. List painful agent jobs.
3. Split each job into record / rim / hands.
4. Run the litmus on rim steps.
5. Map each keeper to a **shape**.
6. Name the SKU (`publisher/capability`).
7. Ask: token/time win vs browse? Envelope useful? Atlas-recommendable?
8. Only then build.

Highest-value specimen tranche is **maximum pattern coverage**, not “30 most
popular APIs.” See [specimen-sky.md](../plan/specimen-sky.md).

## Hard no

Do **not** scout these as public stars (Now / specimen horizon):

| Hard no | Why |
| --- | --- |
| Open-ended taste / ranking (“best laptop,” “best trip”) | Judgment + search engine; not a SKU |
| Fake-review gospel / authenticity marketplace | Adversarial; Yelp-shaped; ADR Not now |
| Unbounded trip / shopping planners | Workshop, not vending machine |
| Full sticky-host clones (Sheets, Gmail, GitHub, airline checkout) | System of record stays elsewhere |
| Local filesystem / shell as public stars | Hands stay on the harness |
| Open-web scrape / arbitrary URL proxy | Legal + safety tarpit; allowlist only |
| Holding funds, inventory, or PII as core product | Different company |
| Embedding winner-picker that selects one star | Violates ADR 0005 |
| Hard product dependency on a single publisher forever | Soft atlas only — [atlas.md](./atlas.md) |

Saga [#76](https://github.com/lbliii/orrery/issues/76) also lists: review-rank
marketplaces · full SoR clones · open-ended planners · local fs/shell public
stars · untrusted isolate sandbox.

## Relationship

- **#76 / specimen plan** — content to put in the sky first.
- **#56 / ADR 0005** — how gaze, resolve, and dual trust work.
- **#77** — this convention freeze (litmus, shapes, atlases).
