# Kida Render

`orrery/kida-render` renders caller-supplied Kida template bytes with JSON
context to an HTML surface and returns stable digests in a signed Envelope.
Transform worker: `allowed_egress = []`, sync in-memory loader, no egress.

## Inputs

| Field | Required | Default | Notes |
| --- | --- | --- | --- |
| `template` | yes | — | Kida template string **or** single `{path, content}` bundle entry |
| `data` | yes | — | JSON object passed to the template context |
| `surface` | no | `html` | v1 supports `html` only |

## Outputs

| Field | Meaning |
| --- | --- |
| `html` | Rendered HTML body (size-capped; no silent truncation) |
| `surface` | Surface enum echoed (`html` in v1) |
| `template_digest` | Lowercase hex sha256 of NFC-normalized UTF-8 template bytes |
| `data_digest` | Lowercase hex sha256 of canonical JSON for `data` |
| `output_digest` | Lowercase hex sha256 of NFC-normalized UTF-8 rendered HTML |

### Digest encoding

- **Template / output:** NFC-normalized string → UTF-8 bytes → sha256 hex.
- **Data:** JSON with sorted keys, compact `,`/`:` separators, NFC-normalized
  strings, UTF-8 bytes → sha256 hex.

## Errors

| Code | Meaning |
| --- | --- |
| `output_too_large` | Rendered HTML exceeds sync cap — includes remediation for future async path |
| `render_timeout` | Wall timeout exceeded |
| `template_too_large` / `data_too_large` | Input exceeds byte caps |
| `surface_invalid` | Non-`html` surface in v1 |

## Direct MCP

`POST /stars/kida-render/mcp` — tool `render`.

## Ops

- No egress.
- Publisher key env: `ORRERY_KIDA_RENDER_KEY_ID` (or shared `ORRERY_STAR_*`).
- Dependency: `kida-templates` (PyPI) on the host.
- Caps: 256 KiB template, 256 KiB data JSON, 256 KiB output, 30s wall timeout.
- Acceptance: `uv run pytest tests/stars/test_kida_render.py -q`

## Demo corpus

Publish corpus renders the fixed Kida README **badge** component with
`{"count": 5, "label": "Messages"}` and expects stable digests plus HTML
containing `<span class="badge">5 Messages</span>`.
