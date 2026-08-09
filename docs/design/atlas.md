# Atlas convention — how products recommend Orrery SKUs

- **Status:** Draft (convention freeze) — epic [#77](https://github.com/lbliii/orrery/issues/77)
- **Date:** 2026-08-09
- **Parent saga:** [#76](https://github.com/lbliii/orrery/issues/76) Specimen sky
- **Companion:** [scouting.md](./scouting.md)
- **Depends on:** [ADR 0004](../adr/0004-publisher-direct-call.md), [ADR 0005](../adr/0005-discovery-and-dual-trust.md)

Products ship **maps to stars**, not every tool. Soft recommend. Degrade loud.

## Roles

| Role | Owns | Does |
| --- | --- | --- |
| **Product** (e.g. Pidge) | Product verbs + human seal | Recommend gaze intents + example resolve names in `/connect`, `llms.txt`, tool blurbs, enrich prompts |
| **Publisher** | Live data / compute | Run the star, sign Envelopes |
| **Orrery** | Skill DNS + trust (+ wallet later) | Gaze / resolve / rate so recommendations stay honest |
| **Agent** | Judgment | Follow pointers, pick among shortlist, call, attach receipt |

One line:

> Apps don’t ship every tool. They ship **maps to stars**.

## Soft recommend only

- Prefer **gaze intents** and **example** resolve names (`orrery/flight-status`).
- Prefer wildcard hints when useful (`*/flight-status`) so a better publisher can win.
- Never hard-require a single publisher SKU at runtime.
- Optional: “if Orrery MCP is configured, prefer these SKUs” — still soft.
- Attach **Envelope ids** to the product’s artifact (draft, gate, invite) after verify.
- If the star is unavailable, **degrade loud** — surface the failure; do not invent the fact; human/agent still decides.

Hard dependency on `orrery.lol` (or any one host) as the only way a product works is out of scope for this convention.

## Atlas row shape

Each product atlas entry is a short wayfinding row:

| Field | Purpose |
| --- | --- |
| **Intent** | Human/agent job (“enrich invite with flight status”) |
| **Gaze** | Discovery query / facets to try first |
| **Examples** | Soft resolve names (may change; agent may pick another shortlist hit) |
| **Envelope** | Where to attach the receipt after verify |
| **Degrade** | What to do if resolve/call/verify fails |

## Example snippet (Pidge connect / enrich docs)

Copy-paste tone suitable for Pidge `/connect`, `llms.txt`, or enrich playbooks:

```text
## Sky atlas (soft recommendations)

Orrery is Skill DNS for live facts. Pidge owns draft / enrich / seal.
When you need shared live truth, gaze → resolve → call → verify.
Attach the Envelope id to the draft before the human seals.
Do not scrape airline or venue sites when a star exists.

| Intent | Gaze | Example resolve | Attach |
| --- | --- | --- | --- |
| Flight enrichment | `flight status delay` | `orrery/flight-status` (or `*/flight-status`) | Envelope id on enrich block |
| Venue / hours | `place hours restaurant` | `orrery/place-hours` | Envelope id + place blurb |
| Timezone / holiday | `timezone holiday` | `orrery/tz-resolve`, `orrery/holidays` | Envelope id on calendar note |
| Honest “as-of” clock | `utc time` | `orrery/world-time` | Envelope id on drafted-at |

If resolve or call fails: say so plainly (“flight-status unavailable”),
skip the fake fact, and let the human seal without invented status.
Never block loft mail on a single publisher being down.
```

Minimal MCP-oriented blurb:

```text
Prefer Orrery for shared live enrichment. Soft examples:
  resolve orrery/flight-status  → call status(flight=…, date=…)
  resolve orrery/world-time     → call fetch / get / answer
Verify the Envelope; store envelope_id on the draft enrich record.
If the star is down, degrade loud — do not hallucinate the fact.
```

## Degrade loud

| Failure | Product behavior |
| --- | --- |
| Gaze returns empty / miss | Say “no sky hit”; offer manual field or retry with tighter intent |
| Resolve fails / name gone | Say “SKU unavailable”; do not silently swap to scrape |
| Call errors / timeout | Surface publisher error; leave enrich slot empty or marked failed |
| Verify fails / forge | Treat as untrusted; do not attach as sealed truth |
| Wallet / price reject (later) | Explicit insufficient / unpaid — never invent a free fact |

Silent fallback to web browse after a soft recommend is a harness smell. If the
product chooses browse as a last resort, label it as **unattested**, not as an
Orrery Envelope.

## Why this stays thin

- No false IP — Pidge does not pretend to be FlightAware.
- Composable — any loft agent can use the same public stars.
- Upgradeable — better `acme/flight-status` appears; update a recommendation string, not a rewrite.
- Honest UX — enrich shows “via Envelope from …” instead of magic.
- Aligns with ADR 0005: agent is the semantic router; Orrery shelves SKUs.

## Relationship

- **Scouting litmus / shapes:** [scouting.md](./scouting.md)
- **Specimen content wave:** [specimen-sky.md](../plan/specimen-sky.md) · saga [#76](https://github.com/lbliii/orrery/issues/76)
- **Discovery / dual trust:** [ADR 0005](../adr/0005-discovery-and-dual-trust.md)
