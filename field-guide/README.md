# Field guide

Agent-curated shared context for **building** Orrery. This is stigmergy: shape
the environment so the next trajectory is shorter. Product truth still lives in
ADRs, star manifests, and [docs/plan/issue-lifecycle.md](../docs/plan/issue-lifecycle.md).

## Rules

1. Edit [`index.md`](./index.md) only within its stated line budget.
2. Capture **surprises** and durable gotchas — not restatements of ADRs.
3. Prefer one-line pointers to `docs/adr/`, `docs/operations/`, or issues.
4. If a gotcha implies a new product decision, open a **design** issue instead
   of encoding policy here.
5. Humans may prune ruthlessly; agents should replace low-value lines before
   growing the budget.

## When to write here

- A worker hit a non-obvious repo constraint (signing keys, publish gate, Railway split).
- Two approaches collided and the winner is not yet an ADR.
- A megafile or test seam repeatedly causes thrash.

## When not to

- Star contracts → `stars/*/manifest` + ops docs
- Lasting architecture → `docs/adr/`
- Backlog shape → GitHub issues via the lifecycle templates
