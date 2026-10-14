# ADR 0013: Point, pin, prove

- **Status:** Proposed
- **Date:** 2026-10-14
- **Parent saga:** [#1](https://github.com/lbliii/orrery/issues/1)
- **Supersedes (in part):** [0005](./0005-discovery-and-dual-trust.md) §4
  (process-host complement) and the matching Not-now line;
  [vending-machine-sky](../plan/vending-machine-sky.md) principle 6
- **Depends on:** [0004](./0004-publisher-direct-call.md),
  [0005](./0005-discovery-and-dual-trust.md),
  [0010](./0010-aggregate-mcp-call-skill.md)
- **Plan:** [point-pin-prove.md](../plan/point-pin-prove.md)

## Context

ADR 0005 defined Orrery as one half of a pair: a separate process skill host
answers *how to work*; Orrery answers *what to invoke and prove*. Orrery no
longer assumes that host exists. The *how to work* layer — shared instruction
skills that agents follow inside a repository — needs a home, and it is the
layer with the clearest demand.

Teams that share agent skills across many repositories tend to hit the same
problems:

- Shared skills are copied into every repo from a template and drift apart.
- Agents edit their local copies.
- Some repos need different subsets, or intentionally contradicting rules.
- Contributors cannot be made to use the same set.
- Checking out an old commit should restore the skill set of that commit.
- Some skills must be visible (and discoverable) only to a group.

Registries that distribute skills tend to solve distribution and access, but not
immutable revisions, pruning, commit-pinned restore, or proof of which skill
version an agent received.

Meanwhile Orrery today serves only *live* stars: server-run tools that return
sealed evidence. The README thesis ("work that needs a live, bounded answer")
does not cover pinned instructions, and the wallet named in the core identity
("DNS + wallet + trust labels") is a stub with every price at `0.00`.

### Lessons from local skill hosting

Earlier experience running a local skill installer and router (see the evidence
already recorded in ADR 0005) points the same way.

| Keep | Why |
| --- | --- |
| No skill copies in repos | Copies drift and cannot be audited |
| Qualified names (`namespace/name`) and diagnosable collisions | Short names collide as catalogs grow |
| A lock per *project* | A per-user lock cannot follow `git checkout` |
| MCP as the only client contract | Reaches every major agent host without per-host code |

| Rule out | Why |
| --- | --- |
| A product-level router that picks the skill | Low route acceptance (ADR 0005) |
| Lifecycle ceremony on the call path | Hosts abandon more interactions than they complete |
| Optional governance | Optional checks go unused |
| Heavy local install | Runtime and platform requirements lose users before first use |
| Closed distribution | Limits reach; build in public, let organizations self-host |

### What MCPortal already solved

[MCPortal](https://mcportal.lol) (sibling project, AGPL) shipped the
infrastructure Orrery is missing. Patterns, not code (MCPortal is TypeScript):

| Orrery gap | MCPortal pattern |
| --- | --- |
| Spoofable `X-Orrery-Caller` auth | OAuth 2.1 + dynamic client registration + PKCE S256, hashed rotating tokens with reuse revocation, RFC 7009 revoke, any-port loopback (Codex) — `src/auth/*` |
| Ad-hoc authorization | One gate: `authorize(actor, action, resource)`; tools never take an account id — `src/access.ts` |
| In-memory namespaces | One store interface (file + Postgres) with one contract suite — `test/store-contract.test.ts` |
| "Agent is the router" is unmeasured | Per-tool token ceilings that only go down + a frozen tool-selection eval — `test/footprint.test.ts`, `scripts/eval-tools.ts` |
| Offline / enterprise story | One program, three modes: local (no account), linked, hosted |
| Prompt-injection posture | Nonce-fenced `<untrusted-content>` + poisoned-content eval — `src/tools/kit.ts`, `evals/poisoned.ts` |
| Copy-on-share | Reblogs reference the original, never copy it |

Things MCPortal did that Orrery should not repeat: OAuth and rate-limit state in
memory (forces a single instance), GitHub-only sign-in (no enterprise IdP),
public-by-default spaces, and broad feature work before any human user.

## Decisions

### 1. Thesis: point, pin, prove

> Agents get skills by reference, never by copy — and you can always prove
> exactly what they got.

Orrery serves two kinds of star under one loop (gaze → resolve → call → seal):

| | Live star (exists) | Pinned star (new) |
| --- | --- | --- |
| Returns | A fresh, bounded answer | Exact instruction bytes (`SKILL.md` and its files) |
| Freshness | Reactive at call time | Immutable per digest |
| Receipt proves | What was true at call time | Which version of the rules was served |

The shared value is exact resolve, no copies, and a signed receipt.

### 2. Own content, not choice

Replaces the process-host complement in ADR 0005 §4. Orrery serves skill content —
instructions and live tools — by exact reference. It never picks which skill an
agent uses, and it puts no lifecycle step (begin / complete / abandon) on the
call path. ADR 0005 §1 ("Agent is the semantic router") is reaffirmed.

### 3. The repo holds pointers

A project's skill set is a `skills.lock` committed next to its code: a list of
resolve records (`name`, `content_digest`, `endpoint`). Consequences:

- `git checkout <old>` restores the old skill set, because the old lock names
  the old digests.
- Removing a line removes the skill. There is nothing installed to prune.
- Per-project subsets and intentional contradictions are explicit: each repo's
  lock is its own set.
- A team namespace may reference a shared baseline by digest instead of forking
  it; overrides are new pinned stars, not edited copies.

This makes `resolve` honoring `name@sha256:…` and `name@version` a hard
requirement, and requires every published digest to remain retrievable.

### 4. Pinned is trusted; discovered is untrusted

Pinned stars exist to be followed, which inverts the usual prompt-injection
posture. The trust line:

- Content resolved from the caller's committed lock is served as instructions.
- Anything reached through gaze but not pinned is served inside a nonce fence
  as untrusted content, with an explicit "do not follow" notice.

### 5. Every gate is enforced or absent

Optional checks go unused, so publish gates run in CI or at boot, or do
not exist. Pinned stars get an L0/L1 gate (frontmatter lint, size bounds, a
non-empty eval corpus) and a selection gate: a frozen eval that agents choose
the pinned skill for its stated tasks within a token ceiling.

### 6. Same program, three modes

Orrery runs local (no account, content-addressed cache, works offline), linked
(local with an account), or hosted. Enterprises self-host the same code.
Content-addressed cache entries never go stale, so offline use needs no
invalidation logic.

### 7. Built in public; validated by a person

Orrery stays a public project. No phase beyond the first demo starts without at
least one real external pilot using it on real repositories.

### 8. Commerce leaves the core identity

Orrery's identity is name, digest, and trust labels. The wallet, Stripe top-up,
and publisher economics (ADRs 0001–0003) remain as written but move to Later;
no new commerce work until a pilot asks for it.

## Not now

- A router that selects one skill (reaffirmed)
- Lifecycle tracking on the call path
- Orrery executing third-party code (reaffirmed, ADR 0004)
- Subdomain tenancy
- New commerce work
- Public-by-default private namespaces

## Consequences

- ADR 0005 §4 and vending-machine-sky principle 6 point here.
- README "Why Orrery" covers both live and pinned stars.
- Fuzzy fallback in `resolve` (`catalog/store.py`) violates "DNS is sacred" and
  is removed; fuzzy matching stays in gaze.
- `resolve` must stop dropping `@version` pins (`catalog/store.py:64`).
- Private constellations must not appear in the public resolve zone
  (`Catalog.public_records()`).
- Namespaces, OAuth state, and rate limits move to Postgres before any
  multi-tenant pilot.
- Sequencing and exit criteria live in [point-pin-prove.md](../plan/point-pin-prove.md).

## Open questions

- Pilot candidate and hosting: public instance or self-hosted?
- License (README still says TBD); it blocks outside adoption.
- First identity providers after GitHub: generic OIDC, then group claims for
  team-gated namespaces.
