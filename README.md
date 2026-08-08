# Orrery

**Skills you point at, not install.**

Gaze to discover, resolve to lock the record, call for a verified result — from any machine, any harness.

Catalogs hand you a repo. Orrery hands you an endpoint, a digest, and a receipt — so the agent can keep moving.

## Status

The product surfaces are implemented as Chirp filesystem-routed pages in [`pages/`](./pages/), at parity with the frozen design mocks:

| Path | Surface |
| --- | --- |
| `/` | Brand hero + the gaze → resolve → call story + live invocation feed |
| `/gaze` | Discovery console (public sky / namespace / constellation nodes) |
| `/resolve` | Skill-DNS resolver zone table + lookup |
| `/stars` | Star detail — manifest, price, signed Envelope receipt |
| `/constellations` | Drawn policy graph + composite receipt |
| `/namespaces` | Private tenancy pitch |
| `/api/resolve?name=` | JSON resolve record (Skill DNS) |

The same process is also a dogfood MCP host ([#964](https://github.com/lbliii/chirp/issues/964) / [#985](https://github.com/lbliii/chirp/issues/985)): aggregated `/mcp`, discovery at `/skills`, a reliability `/console`, three temporary stub skills, and publish-oracle smoke. Resolve records are seeded from the design mocks in [`catalog/`](./catalog/) until the live registry feeds them.

Remaining product work (live MCP wiring, provisioning, commerce) is tracked in **[Saga #1](https://github.com/lbliii/orrery/issues/1)**.

Design mocks (validated direction): [`design/`](./design/). Frozen favorite: [`design/v1-night-gold/`](./design/v1-night-gold/).

## Run locally

```bash
uv sync --group dev
uv run python app.py
```

Open `/` for the brand + live feed, browse `/gaze`, `/resolve`, `/stars`, `/constellations`, `/namespaces`, check reliability at `/console`, or point an MCP client at `/mcp`.

```bash
# List tools (modern Streamable HTTP headers)
curl -s http://localhost:8000/mcp \
  -H 'Content-Type: application/json' \
  -H 'mcp-protocol-version: 2026-07-28' \
  -H 'mcp-method: tools/list' \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1,"params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{}}}}'

# Invoke look_at — watch `/` show the call
curl -s http://localhost:8000/mcp \
  -H 'Content-Type: application/json' \
  -H 'mcp-protocol-version: 2026-07-28' \
  -H 'mcp-method: tools/call' \
  -H 'mcp-name: look_at' \
  -d '{"jsonrpc":"2.0","method":"tools/call","id":2,"params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{}},"name":"look_at","arguments":{"target":"Vega"}}}'
```

Boot runs freeze + smoke against the dogfood corpus so `/console` shows reliability scores. Set `ORRERY_SKIP_PUBLISH=1` to skip that during local iteration.

Copy `.env.example` → `.env` if you want stable signing keys across restarts.

## Test

```bash
uv run pytest
```

## Deploy (Railway)

Live: [https://orrery-production-f7de.up.railway.app](https://orrery-production-f7de.up.railway.app)

`Dockerfile` + `railway.toml` live at the repo root. Merges to `main` rebuild via [`.github/workflows/deploy-railway.yml`](./.github/workflows/deploy-railway.yml) (same pattern as Chirp's Lucky Cat demo): `railway up --ci --service orrery` with a project-scoped `RAILWAY_TOKEN` repo secret.

Manual / first deploy from this directory:

```bash
railway up --ci --service orrery
```

| Variable | Value |
| --- | --- |
| `CHIRP_ENV` | `production` |
| `CHIRP_DEBUG` | `0` |
| `CHIRP_SECRET_KEY` | generated secret |
| `CHIRP_LOG_FORMAT` | `json` |
| `GIT_REF` | `main` (Chirp git ref for the skill stack) |

`AppConfig.from_env()` binds `0.0.0.0:$PORT` on Railway. Healthcheck targets `/health`. Public domain target port must match `$PORT` (8080 on Railway).

## Preview design mocks

```bash
cd design
python -m http.server 8765
# → http://localhost:8765
```

## Dependency note

`chirp.skill` is installed from **Chirp `main` via git** (not PyPI yet). The Dockerfile pins the same via `GIT_REF`.

## License

TBD.
