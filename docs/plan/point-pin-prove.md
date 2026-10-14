# Plan: Point, pin, prove

- **Status:** Draft
- **Date:** 2026-10-14
- **ADR:** [0013-point-pin-prove.md](../adr/0013-point-pin-prove.md)
- **Supersedes in part:** [vending-machine-sky](./vending-machine-sky.md)
  principle 6; Sprint 5 (economics) moves to Later

## North-star demo

A repository commits `skills.lock`. An agent in Cursor or Codex follows the
pinned skills. `git checkout` to an older commit, and the agent gets the older
skill set — every fetch backed by a signed receipt naming the digest served.

Every phase below is ordered to reach that demo first, then make it safe for
real teams.

## Phases

| Phase | Focus | Ships independently? | Gate to start |
| --- | --- | --- | --- |
| **0** | Re-baseline + correctness fixes | Yes | — |
| **1** | Exact, immutable versions | Yes | Phase 0 green |
| **2** | Pinned (instruction) stars + selection gate | Yes | Phase 1 |
| **3** | `skills.lock` + local mode → **demo** | Yes | Phase 2 |
| **P** | Real pilot lined up | — | Demo recorded |
| **4** | Durable tenancy + real auth + groups | Yes | Pilot committed |
| **5** | Usage evidence from receipts | Yes | Pilot running |

Phases 0–3 can run on the public sky with no auth work. Phase 4 does not start
until a named pilot needs private namespaces (ADR 0013 §7).

---

## Phase 0: Re-baseline

**Goal:** Know the current state and remove violations of existing principles.

### Task 0.1 — Health check

Run `uv run pytest`; confirm orrery.lol is live; record results in the PR.

### Task 0.2 — Resolve is exact

Remove the cross-namespace short-name and substring fallbacks from resolve in
`catalog/store.py`. A bare name qualifies only to `orrery/` (exact, like a
search domain). A pin (`@version` or `@sha256:…`) that does not match the record
is a miss, never dropped. Fuzzy matching stays in gaze only ("DNS is sacred",
vending-machine-sky principle 4).

**Acceptance:** resolve of an unknown or partial name returns not-found; tests
cover partial names, other-namespace short names, and mismatched pins.

**Status:** Done. Follow-up: add gaze suggestions to the not-found response.

### Task 0.3 — No private names in the public zone

`Catalog.public_records()` must not include `visibility == "private"` rows, and
every public resolve surface applies the namespace allowlist: `/api/resolve`,
the `/resolve` page (JSON and `?q=`), MCP `resolve_name` and `gaze_describe`,
and constellation detail.

**Acceptance:** tests assert no private record in the public resolver zone or
`/constellations` index, and that each surface denies an unlisted caller.

**Status:** Done.

### Task 0.4 — License decision

Pick a license (owner decision). Blocks any outside pilot.

---

## Phase 1: Exact, immutable versions

**Goal:** The same pin returns the same bytes, forever.

### Task 1.1 — Version history store

Every publish appends a row keyed by (`name`, `content_digest`); rows are never
overwritten. Postgres behind one store interface with a file backend for
local mode, both run against one contract suite (pattern: MCPortal
`test/store-contract.test.ts`).

### Task 1.2 — Resolve honors pins

`resolve_name` accepts `name`, `name@version`, and `name@sha256:…`. Stop
dropping the pin at `catalog/store.py:64`. Unpinned `name` resolves to the
current digest and says so in the record.

**Acceptance:** resolving a superseded digest returns that digest's record and
bytes; an unknown digest is a hard error, never a fallback.

---

## Phase 2: Pinned stars

**Goal:** Serve instruction skills by digest, with receipts, and prove agents
select them.

### Task 2.1 — `kind = "pinned"` star

A pinned star packages a `SKILL.md` (plus referenced files). Served three ways,
because host support for MCP prompts is uneven:

- MCP `prompts/get` and `resources/read`
- a `get_skill(name, digest)` tool

Each response is a sealed Envelope over the content digest.

### Task 2.2 — Publish gate (L0/L1 for pinned)

Frontmatter lint, size bounds, non-empty eval corpus. Enforced at boot/CI
(ADR 0013 §5).

### Task 2.3 — Selection gate

A frozen eval: for each pinned star, the tasks in its corpus must lead a model
to fetch it, within a per-star token ceiling that only goes down. Pattern:
MCPortal `test/footprint.test.ts` + `scripts/eval-tools.ts`.

**Acceptance:** CI fails on selection regression or ceiling increase.

### Task 2.4 — Trust line

Content resolved from a caller-supplied lock is served as instructions. Content
reached via gaze without a lock entry is wrapped in a nonce-fenced
`<untrusted-content>` block. Poisoned-skill fixtures test both paths. Pattern:
MCPortal `src/tools/kit.ts`, `evals/poisoned.ts`.

---

## Phase 3: The lock and local mode → demo

**Goal:** A repo pins its skill set; `git checkout` switches it.

### Task 3.1 — `skills.lock` format

Spec `orrery-lock/0.1`: list of `{name, content_digest, endpoint}`. Documented
in `docs/design/`.

### Task 3.2 — Lock client

`orrery lock add | sync | verify` as a single-file tool (no heavy runtime;
see ADR 0013 lessons). Alternatively the agent passes the lock to Orrery and Orrery
serves only those digests; support both.

### Task 3.3 — Local mode

Same program, no account. Content-addressed cache keyed by digest, so offline
use needs no invalidation. Optional git `post-checkout` hook runs `verify`.

### Task 3.4 — Demo

Record the north-star demo in Cursor and Codex. Publish it on `/how-it-works`.

---

## Gate P: Pilot

**Goal:** One real external team using pinned stars on real repos before more
infrastructure.

- Candidate profile: many repos, shared skills, drift pain, at least one
  contributor outside the core team.
- If the team cannot put its skills on a public instance, the pilot runs
  self-hosted (local/hosted mode is the same program).
- Exit: the pilot's lock is committed in at least one repo and used for two
  weeks.

---

## Phase 4: Durable tenancy and real auth

**Goal:** A private namespace is invisible and unresolvable without the right
group. Port MCPortal patterns rather than design new ones.

| Task | Pattern source |
| --- | --- |
| 4.1 Namespaces in Postgres (replace `namespaces/store.py` in-memory store) | MCPortal store contract |
| 4.2 OAuth 2.1 + DCR + PKCE, hashed rotating tokens, revoke; any-port loopback | MCPortal `src/auth/*` |
| 4.3 Single `authorize(actor, action, resource)` gate; tools never take caller identity | MCPortal `src/access.ts` |
| 4.4 Group membership gates both resolve **and** gaze (hidden discoverability) | New — MCPortal has no groups |
| 4.5 OAuth pending state and rate limits in Postgres (multi-instance safe) | Avoid MCPortal's in-memory limit |
| 4.6 Generic OIDC; group claims map to namespace access | New |

Remove `X-Orrery-Caller` as an auth mechanism once 4.2–4.3 land.

---

## Phase 5: Usage evidence

**Goal:** An honest usage signal without a router or lifecycle ceremony.

Aggregate receipts per namespace and per lock: which digests were served, when,
to which host. Show it on the namespace page. No begin/complete calls.

---

## Later

- Wallet, Stripe top-up, publisher economics (ADRs 0001–0003)
- Opt-in listing growth (ADR 0012) beyond the newcomer shelf
- Scoped retrieval (vending-machine-sky Sprint 4)

## Not now

See [ADR 0013](../adr/0013-point-pin-prove.md#not-now).

## Risks

| Risk | Mitigation |
| --- | --- |
| More features, still no user | Gate P blocks Phase 4 |
| Agents ignore pinned skills | Selection gate (2.3); receipts show what was actually fetched |
| Pinned content as an injection vector | Trust line (2.4); publish gate (2.2); group-gated namespaces (4.4) |
| Network dependency | Local mode + content-addressed cache (3.3) |
| Single-instance state | 4.5 before any multi-tenant pilot |
| Connector discovery is weak in hosts | The committed lock is the distribution path: every clone introduces Orrery |

## Success metrics

| Metric | Now | After Phase 3 | After Phase 5 |
| --- | --- | --- | --- |
| Pins honored by resolve | No (`@` dropped) | Yes, by version and digest | Yes |
| Instruction skills served | 0 | ≥3 pinned stars | Pilot's set |
| Repos with a committed lock | 0 | Demo repo | ≥1 pilot repo |
| Real external users | 0 | 0 | ≥1 team |
| Private namespace auth | Self-asserted header | Unchanged | OAuth + groups |
