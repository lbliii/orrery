<!--
field-guide inject point — keep the body ≤ 80 lines (excluding this comment).
Budget: 80 lines. Current body should stay scannable in one screen.
-->

# Orrery field guide (index)

Line budget: **80** (body below). Prefer links over essays.

## Build / run

- Local: `uv sync --group dev` then `uv run python app.py` (see root README).
- Faster iteration: `ORRERY_SKIP_PUBLISH=1` skips the publish gate at startup.
- Keys: copy `.env.example` → `.env` or signing keys rotate every process.
- Tests: `uv run pytest`. Leaf acceptance often uses `@pytest.mark.issue(N)`.

## Issue lifecycle (swarm-ready)

- Invokes: [`AGENTS.md`](../AGENTS.md) — say `board`, `burndown`, `claim #N`, …
- Standard: [`docs/plan/issue-lifecycle.md`](../docs/plan/issue-lifecycle.md)
- Workers claim only issues labeled `leaf` **and** `ready`.
- Leaves must list **owned paths** + **machine acceptance**; do not re-decide ADRs.
- Templates: `.github/ISSUE_TEMPLATE/` (saga / epic / design / leaf / bug).

## Architecture pointers

- Control vs data plane: [`docs/adr/0001-control-plane-wallet.md`](../docs/adr/0001-control-plane-wallet.md)
- Publisher-direct call: [`docs/adr/0004-publisher-direct-call.md`](../docs/adr/0004-publisher-direct-call.md)
- Gaze shelf + dual trust: [`docs/adr/0005-discovery-and-dual-trust.md`](../docs/adr/0005-discovery-and-dual-trust.md)
- Managed worker / artifacts: [`docs/architecture/managed-execution.md`](../docs/architecture/managed-execution.md)

## Megafile caution

Prefer leaves that touch `stars/<name>/` + matching tests/ops docs. Treat these
as contention hotspots unless the leaf explicitly owns a carve-out:

- `app.py`, `discovery.py`, `dogfood.py`
- `static/styles.css` (unless brand-scoped)
- shared star registries / package `__init__` wiring

## Surprises (keep short)

- Aggregate `/mcp` may alias colliding tool names; resolve + direct star MCP for
  canonical names.
- Gaze must not return valuable tool payloads — shortlist + facets only.
- Public networked stars are allowlisted and bounded; read the star ops doc
  before widening egress.

## How to add a line

Delete a lower-value bullet first if over budget. Link out; don't paste specs.
