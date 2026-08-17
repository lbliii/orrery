# Agent Plugins (official pointer package)

Orrery ships a portable [Agent Plugins 1.0.0](https://github.com/agentplugins/agent-plugins-spec/blob/main/spec/1.0.0.md)
directory so a conformant client can **point** at the slim discovery MCP.
This is not an install of skills, and Orrery is not a plugin client.

Package root: [`plugins/orrery/`](../../plugins/orrery/).

```text
plugins/orrery/
├── plugin.json
└── mcp.json
```

`mcp.json` declares one `streamable-http` server at
`https://orrery.lol/mcp` (ADR 0010 slim default). There is no `skills/`
tree, no stdio server, and no `PLUGIN_DATA`.

Pinned upstream schemas (do not fetch at load time):
[`plugins/schemas/1.0.0/`](../../plugins/schemas/1.0.0/).

## Not a plugin runtime

Orrery does not discover, install, load, or execute Agent Plugins.
Workers who need a sealed conformance receipt use
`orrery/plugin-preflight` / `orrery/plugin-readiness` over a caller
`{path, content}` bundle. See [agent-plugins-rim](../plan/agent-plugins-rim.md).

## Acceptance

```bash
uv run pytest tests/plugins/test_orrery_plugin.py -q
```
