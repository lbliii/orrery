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

Optional policy fields on create:

```json
{
  "id": "acme",
  "retention_days": 30,
  "caller_allowlist": ["agent:deploy", "agent:ci"]
}
```

- `retention_days` — integer 1–3650 (default `90`); local hook for Envelope
  retention (audit export stubbed).
- `caller_allowlist` — machine caller ids allowed on private namespace paths.
  **Deny-by-default** when non-empty; empty list keeps open access.

Machine clients are CSRF-exempt (same pattern as wallet holds).

| Status | Meaning |
| --- | --- |
| `201` | Namespace created — body includes `id`, `created_at`, `retention_days`, `caller_allowlist` |
| `400` | `invalid_slug`, `reserved_slug`, or `duplicate_namespace` |
| `400` | `invalid_json`, `expected_object`, or `id_required` |
| `400` | `invalid_retention_days` or `invalid_caller_allowlist` |

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

## Caller allowlist + retention (#30)

Private namespace machine paths (`GET /api/resolve?name={ns}/…`, gaze with
`node={ns}`) check the `X-Orrery-Caller` header when the provisioned namespace
has a **non-empty** `caller_allowlist`. Unauthorized callers receive `403`
`caller_not_allowed`. Public sky (`node=public`, public resolve names) is
unchanged.

Retention is read from the namespace store via `retention_days_for(namespace_id)`
for downstream Envelope hooks; no audit export pipeline in this leaf.

## Module

```python
from namespaces import provision_namespace, reset_namespace_store
from catalog import CATALOG

reset_namespace_store()  # tests
result = provision_namespace("acme", catalog=CATALOG)
```

## Verify

```bash
uv run pytest tests/test_namespace_provision.py tests/test_namespace_allowlist.py -q
uv run ruff check .
```

## Page UX (`/namespaces`)

The Create form on `/namespaces` posts to `POST /api/namespaces` from the
browser (Alpine + fetch). The disabled “Coming soon” CTA is replaced by an
enabled slug field and **Create namespace** button.

On `201`:

1. Success panel shows the namespace id and path prefix (`{id}/*`) — scoped
   gaze and resolve on the shared catalog, not a separate hostname promise.
2. Next-step links: Gaze node (`/gaze?node={id}`) and Resolve demo
   (`/resolve?name={id}/demo`).

API `error` codes (`invalid_slug`, `reserved_slug`, `duplicate_namespace`)
surface inline in the form.

Verify page smoke:

```bash
uv run pytest tests/test_pages.py -q -k namespace
```

## Related

- Gaze node scoping: [gaze-namespace-scope.md](./gaze-namespace-scope.md)
