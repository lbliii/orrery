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

The same process is also a dogfood MCP host ([#964](https://github.com/lbliii/chirp/issues/964) / [#985](https://github.com/lbliii/chirp/issues/985)): aggregated `/mcp`, discovery at `/skills`, dogfood skills (gaze, resolve, html-to-pdf, world-time, source-watch, launch-gate), and publish-oracle smoke. **Product trust** is the Resolve/Star oracle pill (`check · freeze · smoke`). Host ops live at `/console` (Chirp reliability console — not part of the night-observatory product chrome). Resolve records are synchronized from the Star registry after the publish gate.

### Reactive star (`orrery/world-time`)

Wave 1 spike ([#37](https://github.com/lbliii/orrery/issues/37)): tools `fetch` / `get` / `answer` pull a **live UTC** reading from a public clock API at call time and seal it in a signed Chirp Envelope. Gaze/resolve show price + blurb only — never the live payload.

**Why cloning fails the value test:** an offline copy of the tool code cannot mint a fresh UTC instant from the upstream clock. Any baked-in datetime is stale by definition; the product is live truth at call time, not a distributable package. (html-to-pdf remains alongside as the Envelope plumbing demo.)

### Star packages and direct MCP

Every callable Star lives in [`stars/`](./stars/) as a versioned capability package: a `star.toml` manifest, framework-free `service.py`, stable `contract.py`, Chirp/MCP `skill.py`, and publish corpus. The host loads those manifests to generate the public resolve records; adding a Star does not require a parallel catalog entry.

Resolve records point at a Star's direct MCP endpoint, where its natural tool names are available without aggregate-host collisions:

| Star | Direct MCP endpoint | Canonical tools |
| --- | --- | --- |
| `orrery/html-to-pdf` | `/stars/html-to-pdf/mcp` | `convert`, `health` |
| `orrery/world-time` | `/stars/world-time/mcp` | `fetch`, `get`, `answer` |
| `orrery/source-watch` | `/stars/source-watch/mcp` | `observe`, `diff`, `answer` |

`/mcp` remains an aggregate compatibility/control-plane surface. It prefixes Source Watch's aggregate `answer` as `source_watch_answer` because world-time already owns that flat tool name; the direct Source Watch endpoint always exposes the canonical `answer`.

### Source Watch star (`orrery/source-watch`)

Source Watch ([#51](https://github.com/lbliii/orrery/issues/51)) fetches an allowlisted official source at call time. Its `observe`, `diff`, and `source_watch_answer` tools produce an attributable canonical URL, content digests, bounded change summaries, or extractive evidence in the signed Envelope payload. V1 admits the Python release notes only; it intentionally rejects arbitrary URLs. (`answer` remains the existing world-time tool on the aggregated MCP host.)

Use it for deployment checks that depend on current upstream guidance: resolve `orrery/source-watch`, call `observe(source="python-release-notes")`, then retain the digest and call `diff` before a later deployment. An offline clone cannot establish whether the official page changed after it was copied.

Remaining product work (live MCP wiring, provisioning, commerce) is tracked in **[Saga #1](https://github.com/lbliii/orrery/issues/1)**.

Strategy ADRs (control plane, prepaid wallet, Stripe top-up):

| ADR | Topic |
| --- | --- |
| [`docs/adr/0001-control-plane-wallet.md`](./docs/adr/0001-control-plane-wallet.md) | Control vs data plane, reactive stars, prepaid wallet, Not now |
| [`docs/adr/0002-prepaid-wallet-ledger.md`](./docs/adr/0002-prepaid-wallet-ledger.md) | Ledger schema, hold/capture, insufficient-balance |
| [`docs/adr/0003-stripe-topup.md`](./docs/adr/0003-stripe-topup.md) | Checkout + webhook credit (design only) |
| [`docs/adr/0004-publisher-direct-call.md`](./docs/adr/0004-publisher-direct-call.md) | Agent → publisher MCP; Orrery is not a proxy |

Design mocks (validated direction): [`design/`](./design/). Frozen favorite: [`design/v1-night-gold/`](./design/v1-night-gold/).

Design language (identity + system inventory): [`docs/design/identity.md`](./docs/design/identity.md) · [`docs/design/system.md`](./docs/design/system.md).

## Run locally

```bash
uv sync --group dev
uv run python app.py
```

Open `/` for the brand + live feed, browse `/gaze`, `/resolve`, `/stars`, `/constellations`, `/namespaces`, or point an MCP client at `/mcp`. Host reliability ops: `/console` (footer **Ops · console**).

```bash
# List tools (modern Streamable HTTP headers)
curl -s http://localhost:8000/mcp \
  -H 'Content-Type: application/json' \
  -H 'mcp-protocol-version: 2026-07-28' \
  -H 'mcp-method: tools/list' \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1,"params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{}}}}'

# Invoke gaze_match — watch `/` show the call
curl -s http://localhost:8000/mcp \
  -H 'Content-Type: application/json' \
  -H 'mcp-protocol-version: 2026-07-28' \
  -H 'mcp-method: tools/call' \
  -H 'mcp-name: gaze_match' \
  -d '{"jsonrpc":"2.0","method":"tools/call","id":2,"params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{}},"name":"gaze_match","arguments":{"intent":"html pdf convert","node":"public"}}}'
```

Boot runs freeze + smoke against the dogfood corpus so `/console` shows reliability scores. Set `ORRERY_SKIP_PUBLISH=1` to skip that during local iteration.

Copy `.env.example` → `.env` if you want stable signing keys across restarts.

## Test

```bash
uv run pytest
```

## Deploy (Railway)

Live: [https://orrery.lol](https://orrery.lol)

Custom domain ``orrery.lol`` is the public HTTP host. Skill DNS resolve records use the same apex as ``mcp://orrery.lol/…`` (override with ``ORRERY_MCP_HOST``).

`Dockerfile` + `railway.toml` live at the repo root. The Railway service is connected to `lbliii/orrery`; merges to `main` rebuild and redeploy automatically (same as pidge). The image install layer re-fetches Chirp at `GIT_REF` because the Dockerfile cache-busts against GitHub's commits API.

Manual / first deploy from this directory:

```bash
railway up --service orrery
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
