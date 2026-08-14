# Sky vitals persistence

Public sky vitals (`GET /api/sky/vitals`, homepage strip) use an in-process
`SkyVitalsStore` by default. Phase 2 adds optional Redis persistence and a
7-day top-resolved-star rollup.

## Environment

| Variable | Effect |
| --- | --- |
| unset / empty `REDIS_URL` | In-process only; counters reset on restart |
| `REDIS_URL` set | Counters and resolve-name events persist under `orrery:sky-vitals:` |

Use the same Redis instance as managed runs when both are enabled on a host.
There is no SQLite or disk fallback.

## Redis keys

| Key | Contents |
| --- | --- |
| `orrery:sky-vitals:state` | JSON blob: rolling invocation/seal timestamps and 7d resolve-name events |

## Phase-2 API extension

When resolve activity exists in the last 7 days, `activity.top_resolved_7d`
may appear (max 5 entries). Phase-1 keys are unchanged. No visitor or user
metrics are collected.

## Operations

- **Restart:** With Redis configured, 24h activity counters and 7d resolve
  rollups survive web process restarts.
- **Flush:** Delete `orrery:sky-vitals:state` to reset persisted vitals
  without touching run queue keys (`orrery:runs:*`).
- **Degraded:** Without `REDIS_URL`, each web process keeps counters in memory
  only (phase-1 behavior).

Design freeze: [sky vitals homepage](../design/sky-vitals-homepage.md).
