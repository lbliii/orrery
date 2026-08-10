# Orrery Boundary

Optional **locality** MCP adapter (`locality: hybrid`). It inventories a local
git SHA and operator-signs a write-authority witness; hosted Orrery protocol
stars still seal and verify. This package is **not** registered in the hosted
agent-card registry.

## Tools

| Tool | Output consumed by |
| --- | --- |
| `local/export-at-ref` | [`orrery/manifest-bind`](../../docs/operations/manifest-bind.md) |
| `local/witness-approve` | [`orrery/write-authority-check`](../../docs/operations/write-authority-check.md) |

## Install (Cursor / Claude Code)

One JSON snippet — paste into MCP settings (replace the absolute path):

```json
{
  "mcpServers": {
    "orrery-boundary": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/ABS/PATH/TO/orrery/packages/orrery-boundary",
        "python",
        "-m",
        "orrery_boundary"
      ],
      "env": {
        "ORRERY_BOUNDARY_WITNESS_PRIVATE_KEY": "<64-char-hex-ed25519-seed>",
        "ORRERY_BOUNDARY_WITNESS_KEY_ID": "orrery-boundary-witness-1"
      }
    }
  }
}
```

## Smoke

From the Orrery repo root (uses in-process hosted stars for validation):

```bash
uv run pytest packages/orrery-boundary/tests -q
uv run ruff check packages/orrery-boundary
```

## Env

| Variable | Purpose |
| --- | --- |
| `ORRERY_BOUNDARY_WITNESS_PRIVATE_KEY` | 64-char hex Ed25519 seed for `local/witness-approve` |
| `ORRERY_BOUNDARY_WITNESS_KEY_ID` | Optional key id (default `orrery-boundary-witness-1`) |
