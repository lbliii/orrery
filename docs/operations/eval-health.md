# Eval health (L3 composite)

L3 **eval health** is an optional quiet composite on gaze ``trust`` that
summarizes supply-side publish-oracle status and demand-side satisfaction
aggregates. It does not replace the separate oracle or satisfaction pills.

## Wire shape

Gaze hits expose three trust siblings:

```json
{
  "trust": {
    "oracle": { "ok": true, "pill_text": "check · freeze · smoke", "...": "..." },
    "satisfaction": { "quiet": true },
    "eval_health": { "quiet": true }
  }
}
```

When both supply is scored (publish receipt present) and digest-matched demand
ratings exist:

```json
{
  "eval_health": {
    "quiet": false,
    "narrative": "supply verified · 75% useful · 4/7d",
    "supply_ok": true,
    "demand": true
  }
}
```

## Quiet empty state

``eval_health`` is **quiet** (``{"quiet": true}`` only — no numeric
placeholders) when:

- There are no digest-matched satisfaction ratings for the live
  ``content_digest``, **and**
- The publish oracle is unscored (no host publish receipt in-process).

Digest-mismatched ratings do not count toward demand; see
[satisfaction schema](../design/satisfaction-schema.md) (#67).

## Related surfaces

| Surface | Field | Notes |
| --- | --- | --- |
| Gaze hit / API | ``trust.eval_health`` | Composite narrative |
| Gaze hit / API | ``trust.oracle`` | Supply-side pill — unchanged (#69) |
| Gaze hit / API | ``trust.satisfaction`` | Demand pill — unchanged (#69) |

## References

- Satisfaction record shape: [satisfaction-schema.md](../design/satisfaction-schema.md) (#67)
- Demand pills: [satisfaction-pills.md](./satisfaction-pills.md) (#69)
- L3 plan: [star-eval.md](../plan/star-eval.md) Sprint 4 (#120)
