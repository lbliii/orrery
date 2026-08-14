# Design: Sky vitals homepage metrics

- **Status:** Accepted (planner freeze)
- **Date:** 2026-08-14
- **Design issue:** [#406](https://github.com/lbliii/orrery/issues/406)
- **Parent epic:** [#405](https://github.com/lbliii/orrery/issues/405)
- **Binds:** [ADR 0005](../adr/0005-discovery-and-dual-trust.md) (public
  anonymous sky)

## Question frozen

What metrics may the public homepage and `GET /api/sky/vitals` expose, under
what labels, and with what JSON schema — given that the public host is
anonymous (no login, no bearer on `/mcp`)?

## Decision

Honest **host-truth aggregates** only. No IP / fingerprint “unique visitors.”
Identity stays optional (wallet / namespace). Leaves may not rename keys or
invent new public metrics without a new design.

### Public labels (never “users” / “visitors”)

| Label | Source key | Phase |
| --- | --- | --- |
| Stars | `catalog.stars_live` | 1 |
| Constellations | `catalog.constellations_live` | 1 |
| Invocations | `activity.invocations_24h` (strip may also show 1h) | 1 |
| Resolves | `activity.resolves_24h` | 1 |
| Seals | `activity.seals_24h` | 1 |
| Useful (7d) | `demand.useful_7d` | 1 if non-zero; else omit |
| Namespaces | `tenancy.namespaces_live` | 1 if non-zero; else omit |

### Feed phases

`discover` | `resolve` | `call` | `seal`

| Tools | Phase |
| --- | --- |
| `gaze_match`, `gaze_search`, `gaze_describe`, `gaze_list_constellations`, `coverage_check` | discover |
| `resolve_name` | resolve |
| `explain_policy` | seal |
| Everything else (including `call_skill` and publisher tools) | call |

Feed row context: `phase`, `display_line`, `tool_name`, truncated
`arguments`. Args denylist: `html`, `body`, `content`, `note`. Truncate at
120 characters. Quiet empty state: honest “quiet sky” copy — not “Waiting
for…”.

(Feed polish shipped in [#407](https://github.com/lbliii/orrery/issues/407);
this table is the freeze that leaf already followed.)

### `GET /api/sky/vitals`

`Cache-Control: no-store`. JSON shape:

```json
{
  "generated_at": "2026-08-14T14:00:00Z",
  "catalog": {
    "stars_live": 0,
    "constellations_live": 0
  },
  "activity": {
    "invocations_1h": 0,
    "invocations_24h": 0,
    "resolves_24h": 0,
    "seals_24h": 0,
    "last_invocation_at": null
  },
  "demand": {
    "useful_7d": 0
  },
  "tenancy": {
    "namespaces_live": 0
  }
}
```

Required keys for phase 1: `generated_at`, `catalog.stars_live`,
`catalog.constellations_live`, `activity.invocations_1h`,
`activity.invocations_24h`, `activity.resolves_24h`, `activity.seals_24h`,
`activity.last_invocation_at`. `demand` / `tenancy` may be present with
zeros; homepage strip omits those pills when zero.

### Phase 1 store

In-process `SkyVitalsStore` subscribed to `tool_events` plus successful
envelope verify. No Redis / disk. Rolling windows by event timestamp.
Catalog counts from the live builtin registry at read time.

### Phase 2 (persist + top resolved)

Leaf [#410](https://github.com/lbliii/orrery/issues/410) adds optional
persistence and a 7-day resolve rollup without changing phase-1 keys.

| Label | Source key | Phase |
| --- | --- | --- |
| Top resolved (7d) | `activity.top_resolved_7d[]` | 2 |

When present, `activity.top_resolved_7d` is an array of at most five objects
`{"name": "<resolved star name>", "resolves": <count>}` sorted by count
descending, then name ascending. Counts come from `resolve_name` tool
arguments within a rolling 7-day window. Omit the key when empty.

**Store:** When `REDIS_URL` is set (same env as managed runs), counters and
resolve-name events persist under the `orrery:sky-vitals:` key prefix and
survive process restarts. When unset, behavior matches phase 1 (in-process
only). No SQLite. See [sky vitals ops](../operations/sky-vitals.md).

## What leaves may assume

- [#408](https://github.com/lbliii/orrery/issues/408) — store + `GET /api/sky/vitals`
- [#409](https://github.com/lbliii/orrery/issues/409) — SSR strip using the
  labels and omit-if-zero rules above
- [#410](https://github.com/lbliii/orrery/issues/410) — persistence only after
  phase 1 keys exist
