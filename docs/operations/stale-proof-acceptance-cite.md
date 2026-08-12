# Stale-proof acceptance cite (dogfood)

`orrery/stale-proof` composite receipts may include an `acceptance_cites` array of
lowercase hex `sha256` **acceptance digests** from `orrery/acceptance-bind`
(ADR [0009](../adr/0009-acceptance-receipt.md), constellation subtree
[0007](../adr/0007-constellation-subtree-contract.md)).

## When to cite

When a constellation run depended on a sealed sprint done-contract from
acceptance-bind, the terminal composite receipt MUST list that digest in
`acceptance_cites`. Orrery does not fetch criteria text from the digest — callers
retain the AcceptanceReceipt or ADR.

`acceptance_cites` is parallel to ADR 0006 `cites` (DecisionReceipt digests only).
Do not put acceptance digests in `cites`.

## Dogfood path

Callers seal criteria via `orrery/acceptance-bind`, then pass the returned
`acceptance_digest` into constellation orchestration as `acceptance_cites` on the
terminal composite receipt.

Example (test harness):

```python
from stars.acceptance_bind.service import bind
from catalog.constellation_run import run_constellation

receipt = bind("leaf-321", criteria=[...])
run_constellation(
    bundle,
    constellation="orrery/stale-proof",
    acceptance_cites=[receipt["acceptance_digest"]],
    ...
)
```

## Acceptance

```bash
uv run pytest -q -k 'acceptance_cites or acceptance_bind'
uv run ruff check .
```
