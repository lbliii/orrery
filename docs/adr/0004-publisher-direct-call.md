# ADR 0004: Publisher-direct call path

- **Status:** Accepted
- **Date:** 2026-08-08
- **Issues:** [#6](https://github.com/lbliii/orrery/issues/6), saga [#1](https://github.com/lbliii/orrery/issues/1)
- **Depends on:** [0001](./0001-control-plane-wallet.md)

## Context

Orrery is Skill DNS + trust surfaces. Agents must **resolve** a name, then
**call the publisher MCP endpoint** directly. Orrery must not become a
reverse proxy that executes everyone’s tools.

Dogfood stars on this host (`html-to-pdf`, `world-time`) mount on the same
process for demo convenience. Product resolve records still advertise
publisher-shaped endpoints (`mcp://orrery.dev/s/…`) so the agent loop matches
production.

## Decision

1. **Resolve returns coordinates only** — endpoint, digest, key, price —
   never tool payloads.
2. **Call is always agent → publisher MCP** — aggregated `/mcp` on this
   host is a dogfood/demo publisher, not a product execution proxy.
3. **Trust surfaces stay on Orrery** — publish-oracle scores at `/console`,
   oracle pills on resolve/star, Envelope verify at `/api/envelope/verify`.
4. **Cross-namespace refs are normal** — constellation graphs may reference
   public stars (e.g. `orrery/html-to-pdf*`) while the constellation node
   lives under `acme/*`.

## Consequences

- Star pages state the publisher-direct rule explicitly.
- Oracle pills deep-link to `/console/{skill}` so public trust matches
  reliability scores.
- Future third-party stars only need a resolvable endpoint + Envelope
  signing — no Orrery code path changes.

## Links

- Saga: https://github.com/lbliii/orrery/issues/1
- Epic: https://github.com/lbliii/orrery/issues/6
