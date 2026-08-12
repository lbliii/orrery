# Namespace provisioning (MVP)

Dev-grade create flow for private Skill DNS prefixes (`acme/*`) and gaze/resolve
scoping. Design freeze: [#29](https://github.com/lbliii/orrery/issues/29),
[namespace-provisioning design](../design/namespace-provisioning.md). Routing:
[path / name-prefix](../design/tenant-routing.md) (#28).

## API

```text
POST /api/namespaces
Content-Type: application/json

{"id": "acme"}
```

Machine clients are CSRF-exempt (same pattern as wallet holds).

| Status | Meaning |
| --- | --- |
| `201` | Namespace created — body includes `id`, `created_at`, `retention_days` |
| `400` | `invalid_slug`, `reserved_slug`, or `duplicate_namespace` |
| `400` | `invalid_json`, `expected_object`, or `id_required` |

### Slug rules

- Lowercase DNS-label: `[a-z][a-z0-9-]{1,62}` (2–63 characters).
- Reserved (fail-loud): `orrery`, `public`, `mcp`, `api`, `www`, `gaze`,
  `resolve`, `stars`, `constellations`, `wallet`, `admin`, `system`.

## Provisioning effect

Creating `acme`:

1. Registers namespace metadata in the in-process store (`namespaces/`).
2. Gaze node `acme` lists only records whose namespace equals `acme` (existing
   [#70](https://github.com/lbliii/orrery/issues/70) scoping via
   `catalog.gaze.records_for_gaze_node`).
3. Seeds **one** demo private star (`{id}/demo`) when the catalog has no records
   for that namespace yet. Pre-seeded demo constellations (`acme/*` fixtures)
   skip the seed step.

Persistence matches the wallet ledger MVP bar — in-process only; durable Postgres
is Not now.

## Module

```python
from namespaces import provision_namespace, reset_namespace_store
from catalog import CATALOG

reset_namespace_store()  # tests
result = provision_namespace("acme", catalog=CATALOG)
```

## Verify

```bash
uv run pytest tests/test_namespace_provision.py -q
uv run ruff check .
```

## Related

- Gaze node scoping: [gaze-namespace-scope.md](./gaze-namespace-scope.md)
- `/namespaces` page CTA wiring — separate leaf (out of scope for #382)
