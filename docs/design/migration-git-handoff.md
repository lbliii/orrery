# Design: Authorized local Git/PR migration handoff

- **Status:** Accepted (planner freeze)
- **Date:** 2026-08-11
- **Parent epic:** [#164](https://github.com/lbliii/orrery/issues/164)
- **Implements leaf:** [#180](https://github.com/lbliii/orrery/issues/180)
- **Depends on:** docs constellation proof [#178](https://github.com/lbliii/orrery/issues/178) (merged);
  checkpoint freeze [#152](https://github.com/lbliii/orrery/issues/152)
- **Binds:** ADR 0004 (publisher-direct; Orrery is not the merge bot), ADR 0008
  change bundles / retention_redaction

## Question frozen

How may an optional agent-local adapter apply an already-sealed migration change
bundle in a caller-authorized checkout and prepare a reviewable branch/PR
summary — without Orrery holding repo credentials or performing production merges?

## Decision

### Trust boundary

| Actor | May |
| --- | --- |
| **Orrery** | Verify sealed bundle digest + profile/validation digests; emit a **handoff receipt** with authority result; never store repo tokens or raw source bodies |
| **Caller agent (local)** | Hold checkout path + credentials; apply patch; run pinned local validator; open branch/PR via caller tools |
| **Neither** | Silent production merge; broad “Orrery as GitHub App with write-all” |

### Handoff inputs (required)

- Sealed `change_bundle` digest (content-addressed; must match store)
- Migration `profile` digest / policy id
- Prior constellation run id or composite receipt digest (docs or api-spec path)
- Caller-declared `checkout_root` policy (path allowlist / workspace id) — not a remote URL with embedded secrets
- Explicit `authority` assertion from the authenticated caller (capability / allowlist)

### Handoff steps (normative)

1. **Verify seal** — reject changed, unsealed, or digest-mismatched bundles (`replay_incompatible` / `bundle_unsealed`)
2. **Authorize checkout** — reject paths outside caller policy
3. **Apply locally** — adapter invoked in-process or as a thin local tool; Orrery records only digests + status, not patch text by default
4. **Pinned local validate** — run the profile’s validator identity; record `local_validation_digest`
5. **Prepare reviewable summary** — branch name + PR title/body digests or refs supplied by caller tools; Orrery stores references only
6. **Handoff receipt** — `{ repo_identity_policy, bundle_digest, local_validation_digest, branch_or_pr_ref, authority_result }`

### Fail closed

Reject when: bundle digest drifts; checkout unauthorized; local validation
mismatches sealed validation expectations; authority missing/expired. Never
persist repository tokens or full source bodies in receipt state (ADR 0008
retention_redaction).

### Non-goals

- Orrery-operated GitHub merge queue / swarm VCS (ADR 0004/0005)
- Replacing constellation pause/resume (#152)
- Inventing a second change-bundle format

## What leaf #180 may assume

- New module under `stars/` or `stars/_core/` (e.g. `stars/migration_git_handoff/` or
  `stars/_core/migration_handoff.py`) plus tests + short ops doc
- May consume sealed shapes from #178 / migration run store; must not reimplement
  docs or api-spec constellation graphs
- Carve-outs for card/skill registration only if exposed as an MCP star;
  prefer a callable star with explicit non-goals in the card blurb
