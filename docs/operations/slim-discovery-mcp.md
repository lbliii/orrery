# Slim discovery MCP (default install)

Default advertised MCP at ``/mcp`` is **gaze, resolve, policy explain, plus one
execution proxy** — not a flat star call zoo ([#302](https://github.com/lbliii/orrery/issues/302),
[design freeze](../design/slim-discovery-mcp.md), [ADR 0010](../adr/0010-aggregate-mcp-call-skill.md)).

## Allowlist (`tools/list` on advertised install)

- ``gaze_match``, ``gaze_search``, ``gaze_describe``, ``gaze_list_constellations``
- ``resolve_name``
- ``coverage_check``
- ``explain_policy``
- ``call_skill`` — same-origin publisher forwarder (ADR 0010)
- ``index_ping``, ``rate_listing`` — opt-in newcomer shelf (ADR 0012)

Star **call** tools (``convert``, ``fetch``, ``run``, ``answer``, …) are absent
from the default install catalog. After ``resolve_name``, call the publisher MCP
endpoint from the Skill DNS record (ADR 0004), or use ``call_skill`` on aggregate
``/mcp`` when the resolved endpoint is same-origin on this host.

For local teaching-trio / constellation demos on this host, call tools also
live on a labeled aggregate at ``/mcp/dogfood`` (not referenced by ``/connect``
or the server-card ``transport.endpoint``). Prefer direct star mounts such as
``/stars/html-to-pdf/mcp`` when exercising publisher-direct call (ADR 0004).

## Copy contract

Server card, ``/connect``, and ``llms.txt`` state:

> This MCP is gaze/resolve (shelf + Skill DNS) plus one call_skill proxy.
> Publisher-direct mounts remain canonical for execution.

``discovery.MCP_TOOLS`` and the server card ``tools[]`` must stay in sync.

## Verify

```bash
uv run pytest tests/test_call_skill_proxy.py tests/test_discovery.py tests/test_app.py -q -k "mcp or call_skill or slim"
uv run ruff check .
```
