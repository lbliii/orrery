# Slim discovery MCP (default install)

Default advertised MCP at ``/mcp`` is **discovery-only** — gaze, resolve, and
policy explain — not a flat star call zoo ([#302](https://github.com/lbliii/orrery/issues/302),
[design freeze](../design/slim-discovery-mcp.md)).

## Allowlist (`tools/list` on advertised install)

- ``gaze_match``, ``gaze_search``, ``gaze_describe``, ``gaze_list_constellations``
- ``resolve_name``
- ``coverage_check``
- ``explain_policy``

Star **call** tools (``convert``, ``fetch``, ``run``, ``answer``, …) are absent
from the default install catalog. After ``resolve_name``, call the publisher MCP
endpoint from the Skill DNS record (ADR 0004).

## Copy contract

Server card, ``/connect``, and ``llms.txt`` state:

> This MCP is gaze/resolve (shelf + Skill DNS). Call the resolved publisher
> endpoint for execution.

``discovery.MCP_TOOLS`` and the server card ``tools[]`` must stay in sync.

## Verify

```bash
uv run pytest tests/test_discovery.py -q
uv run ruff check .
```
