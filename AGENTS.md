# AGENTS.md

How to work on this repo with agents.

**Default:** you talk to the **orchestrator** (this chat). It reads the board,
plans, and **delegates** planner/worker work to subagents. You should not have
to say `claim #N` unless you want a single-leaf escape hatch.

| Doc | Role |
| --- | --- |
| [`docs/plan/issue-lifecycle.md`](docs/plan/issue-lifecycle.md) | Saga → epic → design → leaf standard |
| [`docs/plan/tree-handling-rim.md`](docs/plan/tree-handling-rim.md) | Product: sealed leaves for *any* agent tree |
| [`field-guide/index.md`](field-guide/index.md) | Budgeted surprises while building Orrery |
| [`.github/ISSUE_TEMPLATE/`](.github/ISSUE_TEMPLATE/) | Intake forms |
| [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md) | PR shape |

**Invariant:** Workers claim only GitHub issues labeled `leaf` **and** `ready`.
Planners own `saga` / `epic` / `design`. Do not re-decide ADRs in a leaf.

---

## Simple invokes

| You say | Mode | What happens |
| --- | --- | --- |
| **`swarm`** / **`drive`** / **`orchestrate`** | **Orchestrator (default)** | Parent stays in this chat; runs board → plan/unblock → delegate workers via subagents; loops until cap or you stop |
| **`swarm #N`** / **`drive epic #N`** / **`drive saga #N`** | Orchestrator scoped | Same, but only that epic/saga subtree |
| **`board`** / **`status`** | Read-only | Counts + ready list; no edits |
| **`burndown`** / **`unblock`** | Planner-only | Unblock queue (no product code); may be a subagent |
| **`plan #N`** | Planner-only | Design/epic freeze; usually a subagent |
| **`claim #N`** / **`work #N`** / **`ship #N`** | Worker escape hatch | Single leaf in-process or one subagent — use when you want to pin one issue |
| **`triage #N`** | Planner escape hatch | Make one issue swarm-ready |

If you give a goal in plain language (“push tree-handling”, “clear wave:1 ready
queue”), treat it as **`swarm`** with that scope — not a request that *you*
micro-claim leaves.

---

## Orchestrator mode (default contract)

The parent agent in this chat is the **orchestrator**. It does **not** implement
every leaf itself when parallel work is possible.

### Responsibilities (parent)

1. **Board** — `gh` summary: ready / blocked / open designs; pick the active
   saga/epic (default bias: [#237](https://github.com/lbliii/orrery/issues/237)
   tree-handling, then [#124](https://github.com/lbliii/orrery/issues/124),
   [#160](https://github.com/lbliii/orrery/issues/160), [#1](https://github.com/lbliii/orrery/issues/1)).
2. **Plan gate** — If ready queue is empty or leaves lack owned paths, run or
   delegate **planner** work first (`burndown` / `plan #N` / `triage`).
3. **Delegate workers** — For each `leaf`+`ready` in scope (respect caps), launch
   a **Task subagent** with the worker contract below. Prefer **parallel**
   subagents when owned paths do not overlap.
4. **Integrate** — Track PRs, merge when asked (or when you said “drive to
   merge”), close issues, **drop `ready` on close**, refresh the board, report
   status in plain language. Prefer fixing worker CI (often ruff) in-branch
   over re-delegating the whole leaf.
5. **Stop conditions** — Hit the turn/leaf cap, empty ready queue, path
   conflict, or user interrupt. Caps are intentional pauses — stop and report
   the next ready leaf; do not fake-unblock to keep the swarm busy.

### Caps (per orchestrator turn unless user overrides)

| Knob | Default |
| --- | --- |
| Planner unblocks | ≤5 leaves → `ready`, or ≤2 designs closed |
| Parallel workers | ≤3 subagents (raise only if paths disjoint) |
| Leaves closed this drive | ≤5 unless user says “keep going” / `drive` |
| Megafile conflict | Serialize; do not parallelize overlapping owned paths |

**Plan gate bias:** A closed design/ADR that unblocks many leaves beats shipping
one more half-specified worker. Prefer planner freeze when the ready queue is
empty or leaves lack owned paths / acceptance.

### Status lines

Before each major step, emit one short line, e.g.:

- `Orchestrator: board — 3 ready, 41 blocked`
- `Orchestrator: planner — unblock #244 deps`
- `Orchestrator: worker ×2 — #244, #159`
- `Orchestrator: integrate — PR …`

### Subagent briefs (copy into Task prompts)

**Planner subagent** — read-only product code; may edit issues/ADRs/docs:

```text
You are an Orrery planner. Read AGENTS.md + docs/plan/issue-lifecycle.md.
No star/runtime implementation. Goal: <GOAL>.
Follow the burndown/plan/triage contract. Return: ready now / newly unblocked /
still blocked (why) / ADR paths touched.
```

**Worker subagent** — one leaf only:

```text
You are an Orrery worker. Read AGENTS.md + field-guide/index.md.
Claim ONLY GitHub issue #<N> if labels include leaf AND ready.
Restate outcome, owned paths, frozen decisions, acceptance.
Implement only owned paths; one PR with PR template; run acceptance.
Before push: `uv run ruff check .` (and `--fix` when safe) — CI lint is the
usual fail, not pytest.
If paths/acceptance missing, stop and report triage needed — do not invent design.
Do NOT merge; leave PR open for the orchestrator.
Return: PR URL, acceptance command + result, ruff clean, files touched.
```

### Path disjointness

Before parallel `claim`s, compare **Owned paths**. If two leaves both touch
`app.py`, `discovery.py`, `dogfood.py`, the same `stars/<name>/`, or the same
shared package (e.g. both under `stars/_core/`), run them **serially** (or
triage a split). Fixture-only vs star-package leaves are usually safe in
parallel.

---

## Mode contracts (leaf-level — for subagents / escape hatches)

### `board` / `status`

1. `gh issue list` (open) and summarize counts by kind/gate.
2. Print `leaf`+`ready` titles (claimable now).
3. Do not edit issues or code unless asked.

### `burndown` / `unblock` (planner)

1. Read this file + `docs/plan/issue-lifecycle.md` + `field-guide/index.md`.
2. **No product implementation** (no star/runtime code). Issue/ADR/docs edits OK.
3. Prefer active sagas: [#1](https://github.com/lbliii/orrery/issues/1),
   [#237](https://github.com/lbliii/orrery/issues/237) (tree-handling),
   [#160](https://github.com/lbliii/orrery/issues/160) (migration),
   [#124](https://github.com/lbliii/orrery/issues/124) (execution).
4. For each candidate: missing design / ADR / owned paths / acceptance / parent
   gate → fix, file design, or leave blocked with one-line reason.
5. Never fake-unblock. Cap: ≤5 leaves → `ready`, or ≤2 designs closed per pass.
6. End with: **ready now / newly unblocked / still blocked (why)**.

### `plan #N` (planner)

1. Fetch issue `#N`. If it is a leaf, stop and suggest `claim` or `triage`.
2. Freeze the decision; link or write ADR when it outlives the epic.
3. File or update child **leaves** with owned paths + machine acceptance.
4. Set `ready` only when deps are actually clear; otherwise `blocked`.

### `claim #N` / `work #N` / `ship #N` (worker)

1. Fetch `#N`. Abort unless labels include `leaf` and `ready`.
2. Restate: outcome, owned paths, frozen decisions, acceptance command.
3. If owned paths or machine acceptance are missing → stop; suggest `triage #N`.
4. Touch **only** owned paths (megafile carve-outs must be explicit on the issue).
5. Do not invent schema/policy; open a design issue or comment instead.
6. One PR using the PR template; run the acceptance command; report results.
7. **Before push:** `uv run ruff check .` must be clean (fix import order /
   line length locally — do not leave that to the orchestrator).
8. Optional: one field-guide line for a true surprise (respect line budget).
9. Do not merge unless the user pinned `ship #N` with merge intent; default is
   open PR for orchestrator integrate.

### Integrate hygiene (orchestrator / `ship`)

When a leaf PR merges and the issue closes:

1. Remove `ready` (and `blocked` if somehow still present) from the closed issue.
2. Confirm the board’s `leaf`+`ready` list no longer includes it.
3. If the merge unblocks dependents, either flip them to `ready` or leave a
   one-line comment on why they stay `blocked`.

### `triage #N` (planner)

Rewrite or comment so `#N` matches the leaf/design template. Add `leaf` /
`ready` / `blocked` correctly. No feature code in this mode.

---

## Process vs product (stars / constellations)

| Concern | Where it lives | Become a public Star/Constellation? |
| --- | --- | --- |
| How we burn down *this* GitHub backlog | `AGENTS.md`, issue lifecycle, labels | **No** — harness/process, not a toll on live truth |
| Orchestrator / subagent delegation | `AGENTS.md` (this file) | **No** — Cursor harness, not Orrery SKUs |
| Field guide / surprises while building Orrery | `field-guide/` | **No** — repo stigmergy |
| Saga/epic/design templates | `.github/ISSUE_TEMPLATE/` | **No** |
| Sealed fact a *any* agent hangs on its tree | `stars/` | **Yes** — gaze → resolve → call → seal |
| Citeable planner freeze for callers | `decision-bind` (saga [#237](https://github.com/lbliii/orrery/issues/237)) | **Yes** — product rim |
| Manifest / patch / structure checks on caller bytes | protocol stars (#222–#224) | **Yes** |
| Frozen multi-step policy graph with composite receipt | constellation | **Yes** — “frozen planner subtree,” not our GitHub board |
| Pick next GitHub issue / merge conflicts / swarm VCS | — | **Never** — out of scope (ADR 0004/0005) |

**Rule of thumb:** If only Orrery maintainers need it to ship this repo, keep it
in `AGENTS.md` / GitHub. If any external agent would pay for a bounded sealed
result mid-tree, it belongs on the [tree-handling rim](docs/plan/tree-handling-rim.md).

---

## Session hygiene

- **Stay in one orchestrator chat** for `swarm` / `drive` — subagents get fresh
  context via Task; you should not open a new chat per leaf.
- New chat is still fine for a clean `board` glance or a pinned `claim #N`
  escape hatch.
- Prefer inexpensive models for worker subagents when the leaf is explicit;
  frontier for orchestrator judgment and planner freezes.
