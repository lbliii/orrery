# Gaze node namespace scope

Active gaze nodes bind ``gaze_match`` and ``gaze_search`` to either the **public
sky** or a **private namespace prefix** ([#70](https://github.com/lbliii/orrery/issues/70),
[tenant-routing design](../design/tenant-routing.md)). Private star names never
appear in public gaze results.

## Node model

| Node id | Scope | Visible records |
| --- | --- | --- |
| ``public`` (default) | ``orrery/*`` public sky | ``visibility == "public"`` |
| ``acme`` (example) | ``acme/*`` tenant sky | ``namespace == "acme"`` |

Unset or empty ``node`` normalizes to ``public``.

## API / MCP

- ``GET /api/gaze/match?intent=…&node=public``
- ``GET /api/gaze/search?q=…&node=acme``
- MCP ``gaze_match`` / ``gaze_search`` accept ``node`` (default ``public``).

Implementation: ``catalog.gaze.records_for_gaze_node`` filters the shared
resolve index before ranking or substring search.

## Verify

```bash
uv run pytest tests/test_gaze.py tests/test_pages.py -q -k 'namespace or gaze or match'
```

Public search for ``acme`` must return zero ``acme/*`` hits; namespace node
``acme`` returns only ``acme/*`` records.
