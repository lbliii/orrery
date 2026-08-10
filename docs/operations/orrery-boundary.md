# Orrery Boundary (optional locality)

Thin MCP adapter package under `packages/orrery-boundary/`. It is **optional
locality**, not a hosted Orrery service: callers export local git inventories
and approve witness envelopes; hosted protocol stars still bind and verify.

## Tools

| Local tool | Hosted consumer | Ops |
| --- | --- | --- |
| `local/export-at-ref` | `orrery/manifest-bind` | [manifest-bind.md](./manifest-bind.md) |
| `local/witness-approve` | `orrery/write-authority-check` | [write-authority-check.md](./write-authority-check.md) |

Do not invent alternate manifest or witness schemas — reuse the contracts
above (`FILE_ENTRY_SCHEMA`; Chirp Envelope payload with `grant_digest` +
`allowed_paths`).

## Locality

- Cards / README mark `locality: hybrid`.
- Not added to the hosted agent-card / builtin registry (ADR 0004 / 0005;
  tree-handling rim).

## Smoke

```bash
uv run pytest packages/orrery-boundary/tests -q
uv run ruff check packages/orrery-boundary
```

Package README: [`packages/orrery-boundary/README.md`](../../packages/orrery-boundary/README.md).
