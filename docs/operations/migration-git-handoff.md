# Migration Git handoff

`orrery/migration-git-handoff` verifies an already-sealed migration change bundle
and emits a **digest-only handoff receipt** for a caller-authorized local checkout.
Orrery never holds repository credentials, applies patches to disk, or performs
production merges (ADR 0004).

## Trust boundary

| Actor | Role |
| --- | --- |
| Orrery | Verify bundle/profile/validation digests; check checkout + authority; seal receipt |
| Caller agent | Hold checkout path + credentials; apply patch locally; run pinned validator; open branch/PR |

## Inputs

| Field | Required | Notes |
| --- | --- | --- |
| `profile` | yes | Pinned MigrationProfile v1 |
| `change_bundle` | yes | Sealed ADR 0008 apply artifact (`bundle_digest` + file entry digests) |
| `repo_identity_policy` | yes | `orrery/checkout-roots@v1` with `allowed_roots[]` + `policy_digest` |
| `checkout_root` | yes | Relative workspace root under policy (no URLs or tokens) |
| `authority` | yes | `orrery/migration-handoff@v1` grant **or** `orrery/explicit-paths@v1` path grant |
| `local_validation` | yes | `validation_digest`, `passed`, optional validator pin |
| `branch_or_pr_ref` | yes | `branch` and/or `pr_ref` plus optional `title_digest` / `body_digest` |
| `sealed_validation_digest` | no | Fail closed when local digest drifts from sealed validate stage |
| `composite_receipt_digest` | no | Prior constellation composite receipt digest |

## Outputs

| Field | Meaning |
| --- | --- |
| `handoff_receipt` | `{ repo_identity_policy, bundle_digest, local_validation_digest, branch_or_pr_ref, authority_result, handoff_receipt_digest }` |
| `authorized` | `true` when verification succeeded |

Receipt state is digest-only per ADR 0008 retention_redaction — no repository
tokens, patch text, or raw source bodies.

## Fail closed

- `bundle_unsealed` / `bundle_digest_mismatch` — changed or incomplete bundle
- `checkout_unauthorized` — root outside policy or traversal/URL embedded
- `authority_denied` / `authority_expired` — missing or stale grant
- `validation_mismatch` — local validator failed or sealed digest drift

## Direct MCP

`POST /stars/migration-git-handoff/mcp` — tool `handoff`.

## Acceptance

```bash
uv run pytest tests/stars/test_migration_git_handoff.py -q
uv run ruff check .
```
