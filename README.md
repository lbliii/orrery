# Orrery

**Skills you point at, not install.**

![A brass orrery set against a sparse midnight sky.](./docs/assets/orrery-hero.png)

[Orrery](https://orrery.lol) is a public sky of small, bounded MCP capabilities that return current evidence and signed receipts. An agent can discover a capability, lock its exact record, call the advertised endpoint, and keep a verifiable result—without cloning a repository or trusting a catalog description as the result.

## Why Orrery

An installed package is a copy: its source, data, and output can all be stale. Orrery is for work that needs a live, bounded answer and evidence of what happened at call time—current UTC, an official-source digest, release metadata, a certificate-expiry check, or a generated artifact.

The public sky is deliberately narrow. Stars declare their tool surface, egress policy, freshness model, and receipt algorithm in [`stars/`](./stars/). Calls return only within that contract.

## Start here

Browse the live sky at [orrery.lol](https://orrery.lol), or give an MCP client the aggregate endpoint:

```text
https://orrery.lol/mcp
```

The HTTP transport is standard Streamable HTTP MCP. For a local instance:

```bash
curl -s http://localhost:8000/mcp \
  -H 'Content-Type: application/json' \
  -H 'mcp-protocol-version: 2025-06-18' \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```

For machine-readable entry points, see [`/connect`](https://orrery.lol/connect), [`/llms.txt`](https://orrery.lol/llms.txt), and the [MCP server card](https://orrery.lol/.well-known/mcp/server-card.json).

## The loop: gaze → resolve → call → seal

1. **Gaze** narrows an intent to a bounded shortlist. It returns names, facets, blurbs, and trust labels—not the valuable tool result. Use `gaze_match`, `gaze_search`, `gaze_describe`, or the [Gaze console](https://orrery.lol/gaze).
2. **Resolve** locks an exact name to its endpoint, manifest digest, publisher key, price label, and policy metadata. Use `resolve_name` or [`/api/resolve?name=orrery/world-time`](https://orrery.lol/api/resolve?name=orrery/world-time).
3. **Call** the resolved star's MCP endpoint directly with its canonical tool name.
4. **Seal** the returned Chirp Envelope with the result and its evidence. Public keys are available at [`/.well-known/orrery/keys.json`](https://orrery.lol/.well-known/orrery/keys.json); verification is exposed at `/api/envelope/verify`. Success seals from protocol stars include host attribution inside the signed payload:

```json
"payload": {
  "passed": true,
  "via": {
    "product": "Orrery",
    "sky": "https://orrery.lol",
    "line": "Sealed via Orrery MCP"
  }
}
```

Gaze is a shelf, not a router: the agent can re-rank the shortlist. Resolve is exact, so a chosen name has one locked record.

## Public sky

All currently registered public Stars are listed as free. That is a current catalog label, not a promise of future commercial terms.

| Capability | Stars | What they do |
| --- | --- | --- |
| Fresh evidence | `world-time`, `source-watch`, `http-head`, `well-known`, `cert-expiry` | Get live UTC, bounded official-source evidence and digests, HTTP metadata, discovery-document slices, or TLS expiry metadata from named allowlisted targets. |
| Release & standards sources | `pypi-release`, `npm-release`, `gh-release-notes`, `gh-file-at-ref`, `pep-section`, `rfc-section`, `spdx-license` | Retrieve bounded current release, repository, standards, or license information from named official sources. |
| Data checks | `csv-url`, `row-lookup`, `row-validate`, `table-diff` | Fetch bounded typed CSV rows, look up and validate a row, or compare caller-provided table snapshots. |
| Managed artifacts | `html-to-pdf`, `csv-report`, `image-transform` | Render a PDF or queue a CSV report / safe PNG transform on Orrery's managed worker; `submit` creates a run and `result` retrieves its terminal receipt. |

The current direct callable constellations are:

- `ship-check` — bounded release, freshness, and UTC evidence.
- `stale-proof` — fresh UTC plus an official Python release-notes digest.
- `table-fresh` — a fresh bounded flights sample and deterministic table-diff verdict.

Their manifests are the source of truth: [`stars/`](./stars/). The live product also presents discovery and constellation surfaces at [`/gaze`](https://orrery.lol/gaze), [`/resolve`](https://orrery.lol/resolve), [`/stars`](https://orrery.lol/stars), and [`/constellations`](https://orrery.lol/constellations).

## The horizon

The public sky can grow with publishers owning their direct endpoints, while private namespaces organize tenant and capability surfaces. Constellations are frozen planner subgraphs ([ADR 0007](./docs/adr/0007-constellation-subtree-contract.md)); managed execution and commerce can evolve around verified results. See the [vending-machine sky plan](./docs/plan/vending-machine-sky.md), the [tree-handling rim plan](./docs/plan/tree-handling-rim.md) (sealed leaves for agent task trees), and the [publisher direct-call ADR](./docs/adr/0004-publisher-direct-call.md).

## Direct stars and the aggregate host

Resolve records advertise direct, namespaced MCP paths such as:

```text
https://orrery.lol/stars/world-time/mcp
https://orrery.lol/stars/source-watch/mcp
https://orrery.lol/constellations/ship-check/mcp
```

Direct endpoints preserve each star's natural tool names. The aggregate `/mcp` is a convenient discovery and compatibility surface; it has a flat namespace, so collisions may receive an aggregate alias. For example, direct Source Watch exposes `answer`, while the aggregate host exposes that conflicting tool as `source_watch_answer`. Resolve first when correctness of the endpoint and tool contract matters.

## Receipts and boundaries

Every Star declares an Ed25519 receipt algorithm and a freshness policy. A receipt can carry source URLs, digests, bounded evidence, and—for managed artifacts—the artifact checksum and lifecycle result. Verify the Envelope against Orrery's published public-key set before relying on it across a trust boundary.

This is not an open web proxy: networked stars use named allowlists, reject redirects, and enforce response bounds. Some stars are live at call time; others are explicitly pure, static-profile, or caller-provided operations. Read the resolved record and receipt rather than inferring freshness from a name.

Managed artifact bytes are held in private object storage; the API exposes the result and delivery path after the worker completes it. The architecture and retention boundary are documented in [`docs/architecture/managed-execution.md`](./docs/architecture/managed-execution.md) and [`docs/operations/artifact-lifecycle.md`](./docs/operations/artifact-lifecycle.md).

## Contribute / issue lifecycle

Backlog work follows a swarm-ready issue tree: **saga → epic → design → leaf**.
Workers claim only `leaf` + `ready` issues with owned paths and machine
acceptance. Say simple invokes from [`AGENTS.md`](./AGENTS.md) — default **`swarm`** /
**`drive`** (this chat orchestrates; subagents take leaves). Escape hatches:
`board`, `claim #N`, …

- [AGENTS.md](./AGENTS.md) — invoke phrases + mode contracts
- [Issue lifecycle](./docs/plan/issue-lifecycle.md)
- [Issue templates](./.github/ISSUE_TEMPLATE/)
- [Field guide](./field-guide/)

Product bet that pairs with this process: the
[tree-handling rim](./docs/plan/tree-handling-rim.md) (sealed leaves for agent
task trees — saga [#237](https://github.com/lbliii/orrery/issues/237)).

## Develop locally

Requires Python 3.14+ and `uv`.

```bash
uv sync --group dev
uv run python app.py
```

Open `http://localhost:8000`. The normal startup runs the publish gate; use `ORRERY_SKIP_PUBLISH=1` for faster local iteration. Copy `.env.example` to `.env` to retain signing keys between restarts.

```bash
uv run pytest
```

Deployment uses the root [`Dockerfile`](./Dockerfile) and [`railway.toml`](./railway.toml). The deployed system has a public API and a private worker backed by Postgres, Redis, and object storage. See the managed-execution architecture above for the service split.

## Status and license

The public site and its registered Stars are live at [orrery.lol](https://orrery.lol). This repository is an active application project; its dependency on `chirp.skill` currently tracks Chirp `main` from GitHub.

License: **TBD**.
