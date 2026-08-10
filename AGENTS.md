# AGENTS.md

How to work on this repo with agents. Prefer **simple invokes** below over
pasting long prompts.

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

Say one of these (new chat preferred for worker/planner modes):

| You say | Mode | Agent does |
| --- | --- | --- |
| **`board`** / **`status`** | Read-only | Count open saga/epic/design/`leaf+ready`/`leaf+blocked`; list ready titles; one-line burndown hint |
| **`burndown`** | Planner | Unblock the queue (cap ≤5 newly `ready` or ≤2 designs closed). No product code. End with a board |
| **`unblock`** | Planner | Same as burndown, but focus only on flipping `blocked` → `ready` when deps are real |
| **`plan #N`** | Planner | Design/epic `#N` only — freeze decision, ADR if lasting, file child leaves with owned paths + acceptance + `blocked`/`ready` |
| **`claim #N`** / **`work #N`** | Worker | Implement leaf `#N` only if `leaf`+`ready`; restated paths + acceptance; one PR; run acceptance |
| **`ship #N`** | Worker | Alias of `claim #N` with explicit “open PR + fill PR template” |
| **`triage #N`** | Planner | Make issue `#N` swarm-ready (owned paths, acceptance, labels) or explain why it stays blocked — no feature code |

If the user names an issue without a verb (`#158`), default to **`claim #N`** when
it is `leaf`+`ready`, else **`triage #N`**.

---

## Mode contracts

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
7. Optional: one field-guide line for a true surprise (respect line budget).

### `triage #N` (planner)

Rewrite or comment so `#N` matches the leaf/design template. Add `leaf` /
`ready` / `blocked` correctly. No feature code in this mode.

---

## Process vs product (stars / constellations)

| Concern | Where it lives | Become a public Star/Constellation? |
| --- | --- | --- |
| How we burn down *this* GitHub backlog | `AGENTS.md`, issue lifecycle, labels | **No** — harness/process, not a toll on live truth |
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

- **New chat** for each `claim` / `plan` / `burndown` (keep planner and worker
  context separate).
- **One leaf per worker session.**
- Prefer inexpensive models for `claim` when the leaf is explicit; frontier for
  `plan` / `burndown`.
