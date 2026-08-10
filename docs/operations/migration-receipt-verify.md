# Verify a migration receipt without calling Orrery

Composite migration receipts (`migration-receipt/v1`) bind a pinned
`MigrationProfile` and stage digests so a standalone client can recover exact
tool and target pins offline (ADR 0008 §12).

Core helpers live in:

- `stars/_core/migration_validate.py` — validator adapter over a change bundle
- `stars/_core/migration_receipt.py` — seal + body verify

## Seal rules

- Validator failure sets `validation_passed` to `false`.
- `seal_migration_receipt(..., require_success=True)` refuses when validation
  failed — never report a failed validator as a successful migration.
- Diagnostics are bounded by the profile `retention_redaction` limits and omit
  raw `source_bytes` / patch text by default.

## Verify (offline)

1. Verify the Envelope signature per
   [envelope-verification.md](../verification/envelope-verification.md) when the
   receipt is wrapped in an Envelope.
2. Recompute `receipt_digest` as `sha256` of canonical JSON of the receipt
   **excluding** `receipt_digest` and Envelope signature fields
   (`signature`, `alg`, `key_id`). Reject mismatch.
3. Recompute `profile_digest` against the published profile bytes; require match
   with the receipt's `profile_id` / `profile_version` / `profile_digest`.
4. Confirm `target.kind` / `target.version` and transformer/validator
   `name`+`version`+`digest` are present and not floating (`latest`, `*`, …).
5. When stage artifacts are held, recompute their digests and require equality
   with receipt fields (`analysis_digest`, `plan_digest`, `bundle_digest`,
   `validation_digest`).
6. Reject `validation_passed === true` when the validation artifact `passed` is
   false, or when findings include `severity: breaking` with `action: block`.

Recoverable identity fields from a verified receipt:

| Field | Meaning |
| --- | --- |
| `profile_id` / `profile_version` / `profile_digest` | Exact profile pin |
| `target.kind` / `target.version` | Pinned migration target |
| `transformer` / `validator` | `{name, version, digest}` tool pins |

## Acceptance

```bash
uv run pytest tests/stars/test_migration_validate.py tests/stars/test_migration_receipt.py -q
```
