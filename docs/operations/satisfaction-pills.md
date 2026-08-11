# Satisfaction aggregate pills (demand-side)

Demand-side pills sit beside the publish-oracle pill on gaze hits, resolve
surfaces, and star pages. They summarize caller verdicts for the **live**
``content_digest`` only.

## Format

When ratings exist for the current digest within the default window:

```text
94% useful · 12/7d
```

- **94% useful** — share of ``useful`` verdicts in the aggregate.
- **12/7d** — total ratings in the rolling 7-day window.

## Quiet empty state

When there are no digest-matched ratings, the pill is **quiet** (no numeric
placeholder). Wire shape:

```json
{"quiet": true}
```

## Digest change → decay

When a star's live resolve digest changes, ratings keyed to the old digest
**do not** count toward the live pill. Historical ratings remain in the store
for the old digest; the live pill stays quiet until new ratings arrive for the
new digest. See [satisfaction schema](../design/satisfaction-schema.md).

## Surfaces

| Surface | Field |
| --- | --- |
| Gaze hit / API | ``trust.satisfaction`` |
| Star page | ``satisfaction`` (template context) |

Supply-side oracle pills are unchanged — see ``trust.oracle``.
