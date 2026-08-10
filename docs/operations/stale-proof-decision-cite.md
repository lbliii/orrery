# Stale-proof decision cite (dogfood)

`orrery/stale-proof` composite receipts may include a `cites` array of
lowercase hex `sha256` **decision digests** from `orrery/decision-bind`
(ADR [0006](../adr/0006-decision-receipt.md), constellation subtree
[0007](../adr/0007-constellation-subtree-contract.md)).

## When to cite

When a constellation run depended on a planner freeze sealed by decision-bind,
the terminal composite receipt MUST list that digest in `cites`. Orrery does not
fetch statement text from the digest — callers retain the statement or ADR.

## Dogfood path

The aggregate `launch-gate` `run` tool accepts optional `decision_id` and
`decision_statement`. When both are set, Orrery seals the decision via
decision-bind and attaches `decision_digest` to the composite receipt `cites`
field.

Example MCP arguments:

```json
{
  "pages": ["README.md"],
  "constellation": "orrery/stale-proof",
  "decision_id": "planner-freeze-1",
  "decision_statement": "pause for typed decision on unsupported MyST directive; do not invent MDX."
}
```

## Acceptance

```bash
uv run pytest tests/stars/test_decision_cite_dogfood.py -q
```
