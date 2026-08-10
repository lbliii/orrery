# Migration run stages

Core migration stage persistence lives in `stars/_core/migration_run.py` with
profile validation in `stars/_core/migration_profile.py` (ADR 0008).

Stages are explicit modes: `analyze`, `plan`, `apply`, `validate`. Each stage
output is content-addressed and sealed in a `MigrationRunStore` keyed by
`replay_key` (source manifest digest, profile digest, mode, and policy id).

Compatible reruns reuse sealed output for the same key. Incompatible replays
(sealing different bytes under an existing key, or supplying a replay key that
does not match current inputs) are rejected. `apply` consumes only the exact
`plan_digest` from the sealed plan artifact.

Default status and partial receipt payloads omit private source bytes per the
profile's `retention_redaction.receipt_excludes_by_default` list. Composite
receipt sealing is owned by #167.

Acceptance:

```bash
uv run pytest tests/stars/test_migration_profile.py tests/stars/test_migration_run.py -q
```
