# Migration corpus

Synthetic fixture repositories and golden stage digests for
[ADR 0008](../adr/0008-migration-profile-v1.md) profiles. Blocks profile
publication regressions without private customer content.

## Layout

| Path | Role |
| --- | --- |
| `fixtures/migration/profiles/` | Pinned `MigrationProfile` JSON (§13 examples A/B) |
| `fixtures/migration/cases/<id>/source/` | Public synthetic inputs |
| `fixtures/migration/cases/<id>/stages/` | Golden `analysis` / `plan` / `bundle` / `validation` + `.digest` sidecars |
| `fixtures/migration/corpus.v1.json` | Case index + required coverage tags |
| `fixtures/migration/unsafe_harness.v1.json` | Unsafe / edge-case harness index |

## Coverage

The corpus exercises: safe transforms, unsupported semantics, malformed
inputs, cross-file refs, extension metadata, validator failures, replay, and
source redaction.

## Acceptance

```bash
uv run pytest tests/fixtures/test_migration_corpus.py -q
```

Digest rules follow ADR 0008 §8: canonical JSON (sorted keys, `,`/`:` separators,
NFC strings, `ensure_ascii=false`).
