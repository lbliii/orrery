# Plan: GitHub issue lifecycle (swarm-ready specs)

- **Status:** Accepted (process freeze)
- **Date:** 2026-08-10
- **Parent product saga:** [#1](https://github.com/lbliii/orrery/issues/1)
- **Complements:** [vending-machine-sky.md](./vending-machine-sky.md),
  [ADR 0005](../adr/0005-discovery-and-dual-trust.md)
- **Templates:** [`.github/ISSUE_TEMPLATE/`](../../.github/ISSUE_TEMPLATE/)
- **Agent stigmergy:** [`field-guide/`](../../field-guide/)

## Why this matters

Large tasks are trees. A planner that also implements fills its context with
leaf detail and drifts. A worker that also designs re-decides questions already
settled elsewhere. GitHub issues are the durable intent store for Orrery; they
must be **specs that lower into owned leaves**, not human tickets that agents
reinterpret.

Without a lifecycle freeze:

1. Epics stay prose essays; workers invent schema mid-flight.
2. Two leaves touch the same megafile and thrash (`app.py`, `discovery.py`).
3. Exit criteria are checkboxes no CI can grade.
4. Design decisions reappear in every subtree (split-brain).
5. `ready` / `blocked` become decoration instead of the lease gate.

**Fix:** Treat the issue graph as the task tree. Planners own sagas, epics, and
design issues. Workers only claim `leaf` + `ready` issues. Shared ADRs and the
field guide carry decisions and surprises between trajectories.

## Principles

1. **Specs as prompts** — The scarce resource is the right description of
   intent. Issue bodies are the unit of work, not chat history.
2. **Planner never implements; worker never plans** — Design questions stay on
   saga / epic / design issues. Leaves execute frozen acceptance.
3. **One decision owner per subtree** — If two leaves would decide the same
   question, collapse it into a design issue or ADR first.
4. **Owned paths** — Every leaf names the paths it may touch. Hotspots need
   explicit carve-outs or a prior split issue.
5. **Machine exit criteria** — Prefer pytest markers, canaries, fixture suites,
   or documented curl/CI checks over prose-only checkboxes.
6. **`ready` is the lease** — Workers start only on `ready` leaves. Waiting on
   humans or deps uses `blocked` and does not hold an agent lease.
7. **Stigmergy over ceremony** — Capture surprise in `field-guide/` and
   decisions in `docs/adr/`; do not invent workshop process on the hot path.
8. **Complement, don't replace, product ADRs** — This doc governs *how we
   track work*. Product truth stays in ADRs and star manifests.

## Issue tree

```text
saga (north-star thread)
 └── epic (outcome + exit criteria + child map)
      ├── design (freeze one decision / schema / contract)
      └── leaf (owned paths + machine acceptance)
```

| Kind | Label | Role | Opens when | Closes when |
| --- | --- | --- | --- | --- |
| **Saga** | `saga` | Product / strategy thread | A multi-epic north star appears | The thread is obsolete or absorbed |
| **Epic** | `epic` | Outcome-sized subtree | Outcome and exit criteria are known | Exit criteria graded true |
| **Design** | `design` | Planner-owned decision | Ambiguity would otherwise fork leaves | Decision recorded; ADR linked if lasting |
| **Leaf** | `leaf` | Worker-owned unit | Paths + acceptance are frozen | Machine acceptance passes + PR merged |

Bugs use the bug template (still a leaf for lifecycle purposes: owned paths +
repro acceptance). Documentation-only chores may omit `leaf` if they touch no
runtime paths — prefer `leaf` whenever an agent might implement them.

## Required fields by kind

### Saga

- North-star sentence
- Provenance (mocks, ADRs, related sagas)
- Workstream / epic list (links, not a fake checklist of code)
- Architectural boundaries and **Not now**
- Success signal (observable, not aspirational)

### Epic

- `**Parent saga:** #N`
- **Outcome** (one paragraph)
- **Scope** / non-goals
- **Decisions already made** (ADR links or “none — see child design issues”)
- **Child map** (design + leaf issues, or “to be filed after design”)
- **Exit criteria** (gradable)
- Wave label (`wave:0`…`wave:5`) when it tracks a product wave

### Design

- `**Parent epic:** #N`
- Question being frozen
- Options considered (short)
- Decision + consequences
- What leaves may assume after close
- Link or create ADR when the decision outlives the epic

### Leaf

- `**Parent epic:** #N` (or parent design if the leaf only implements that freeze)
- **Outcome** (one sentence)
- **Owned paths** (allowlist of files/dirs the worker may change)
- **Out of scope paths** (optional explicit deny)
- **Decisions frozen** (ADR / design issue cites — do not re-decide)
- **Acceptance** — at least one machine check, for example:
  - `uv run pytest -m issue(N)` or named test module
  - canary script / workflow
  - documented HTTP smoke with expected keys
  - fixture / golden digest update
- Labels: `leaf`, priority, domain (`gaze` / `call` / …), wave, and exactly one
  of `ready` or `blocked`

Optional HTML key for hydration scripts:

```html
<!-- orrery-backlog-key:short-stable-id -->
```

Issue forms capture wave / readiness / priority as fields; **apply the matching
labels after create** (GitHub forms cannot map dropdowns to labels by themselves).

## Label lifecycle

| State | Labels | Meaning |
| --- | --- | --- |
| Planning | `design` or `epic` without `ready` | Planner work; workers do not claim |
| Blocked | `blocked` (remove `ready`) | Dependency or human gate; no worker lease |
| Ready | `ready` (remove `blocked`) | Leaf may be claimed by a worker |
| In flight | assignee or PR link | One worker owner; do not double-claim |
| Done | issue closed | Acceptance true; PR merged or epic exit graded |

Rules:

1. Never put both `ready` and `blocked` on the same issue.
2. Promoting a leaf to `ready` means its design deps are closed or explicitly
   waived on the issue body.
3. Epics may carry `blocked` while children proceed only if the epic exit still
   waits on an external gate — prefer blocking the specific leaf.
4. Priority (`P0`–`P3`) is scheduling, not readiness.

## Ownership and megafiles

Leaves that would edit any of the following need either a narrow owned-path
carve-out or a prior split/refactor leaf:

- `app.py`
- `discovery.py`
- `dogfood.py`
- `static/styles.css` (unless the leaf is brand-scoped)
- package-wide `__init__` registries that every star touches

Prefer “touch only `stars/<name>/` + `tests/stars/…` + ops doc” shaped leaves.

## Planner vs worker operating loop

```text
1. Planner opens / updates epic (outcome + exit).
2. Planner files design issues for contested decisions.
3. Design closes → ADR or in-body decision freeze.
4. Planner files leaves with owned paths + machine acceptance.
5. Planner flips leaves to ready when deps close.
6. Worker claims one ready leaf; implements only owned paths.
7. Worker opens PR citing issue number + acceptance commands.
8. Review lenses: CI, canaries, envelope/verify tests, human on new decisions.
9. On surprise, update field-guide/ (budgeted) or open a design issue — do not
   silently expand leaf scope.
```

Frontier models belong on steps 1–5 and on intentional breakage that needs a
new decision. Inexpensive models belong on step 6 when the leaf is explicit.

## Intentional breakage

If a leaf must change a core contract outside its owned paths:

1. Stop and open or resume a **design** issue (or ADR).
2. Or, if urgency is justified, land a focused patch with an issue comment that
   states *why*, then file follow-up leaves for dependents — same spirit as
   licensing intentional breakage in a swarm, without silent scope creep.

## Review lenses (stacked)

| Lens | Cheap signal |
| --- | --- |
| CI pytest | Default gate |
| Issue marker / named acceptance | Leaf-local grade |
| Public canaries | Live contract still true |
| Envelope / verify tests | Receipt trust boundary |
| Human / planner | New ADR, brand, or pricing only |

No single lens is enough; prefer stacking cheap ones over one expensive reread
of the full transcript.

## Field guide

[`field-guide/`](../../field-guide/) is agent-curated shared context for building
Orrery. `field-guide/index.md` is the inject point. Constraints:

- Line budget enforced in the index header
- Capture **surprises** and durable gotchas, not restatements of ADRs
- Prefer links to ADRs / ops docs over pasting large specs
- Humans may prune; agents may edit within budget

## Templates and scripts

| Asset | Purpose |
| --- | --- |
| `.github/ISSUE_TEMPLATE/*.yml` | Form-enforced required fields |
| `.github/PULL_REQUEST_TEMPLATE.md` | Cite leaf, paths, acceptance |
| `scripts/hydrate_backlog.py` | Historical bulk create (not the day-to-day path) |
| `docs/adr/` | Lasting decisions leaves must cite |
| `docs/design/star-eval.md` | Copy-paste acceptance for new public stars |

## Adoption checklist

- [ ] New work uses the saga / epic / design / leaf templates
- [ ] Open leaves that an agent could start have `leaf` + `ready` or `blocked`
- [ ] Each ready leaf lists owned paths and a machine acceptance command
- [ ] Epics link parent saga and child issues
- [ ] Design decisions that outlive an epic land an ADR
- [ ] PRs fill the PR template and name the acceptance command run
- [ ] Surprises go to `field-guide/` within budget

## Non-goals

- Replacing GitHub with another tracker
- Building an in-house swarm VCS or merge reconciler
- Orrery product routing of “which skill to pick” (ADR 0005)
- Mandatory story points, sprint ceremonies, or SLA theater

## Success signal

A frontier planner can decompose an epic into ready leaves; a cheaper worker
can complete a leaf using only the issue body + cited ADRs + owned paths; CI
grades acceptance without re-reading chat.
