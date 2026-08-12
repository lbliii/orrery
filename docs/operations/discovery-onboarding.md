# Discovery onboarding — three-call agent tour

Frozen starter paths for a first Orrery session ([#393](https://github.com/lbliii/orrery/issues/393)).
ADR 0005: **agent ranks** intents; Orrery **documents** paths — no auto-routing.

## Prerequisite

Point a streamable-HTTP MCP client at ``/mcp`` (see [slim discovery MCP](slim-discovery-mcp.md)).
Default install is gaze/resolve only; call tools live on the **publisher** endpoint
returned by ``resolve_name`` (ADR 0004).

## Tour contract

1. **Gaze** — ``gaze_match`` or ``gaze_search`` with your intent (optional when using
   frozen paths below).
2. **Resolve** — ``resolve_name`` with the SKU from the path table.
3. **Call** — ``run`` on the publisher MCP with the frozen ``arguments``.
4. **Seal** — verify the signed Envelope; check ``expected_disposition``.

In-MCP ``call_skill`` on aggregate ``/mcp`` waits for [#390](https://github.com/lbliii/orrery/issues/390);
until then use direct publisher MCP or the probe scripts in this doc.

## Frozen paths

| Step | Title | Name | Tool | Arguments | Expected |
|------|-------|------|------|-----------|----------|
| 1 | Live truth | ``orrery/stale-proof`` | ``run`` | ``{}`` | ``fresh_proof`` |
| 2 | Ship gate | ``orrery/ship-check`` | ``run`` | ``{"package":"httpx"}`` | ``ready`` |
| 3 | Content gate | ``orrery/content-readiness`` | ``run`` | minimal README bundle | ``needs-work`` |

Machine-readable copy: ``discovery.STARTER_PATHS`` and
[``tests/gaze-starter-paths.v1.json``](../../tests/gaze-starter-paths.v1.json).
Human copy: ``/connect#starter-paths`` and ``/llms.txt`` (Onboarding starter paths).

## Preflight

Before calling allowlist-gated stars, use ``coverage_check`` on aggregate ``/mcp``:

- Ship gate: ``coverage_check`` with ``star=orrery/ship-check``, ``package=httpx`` →
  ``allowed: true``.

Constellations without a named allowlist map (``orrery/stale-proof``,
``orrery/content-readiness``) skip ``coverage_check`` — resolve and call directly.

## Verify

```bash
uv run pytest tests/test_discovery.py -q -k starter
uv run ruff check .
```
