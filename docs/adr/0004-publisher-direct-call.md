# ADR 0004: Publisher-direct call path

- **Status:** Accepted
- **Date:** 2026-08-08
- **Issues:** [#6](https://github.com/lbliii/orrery/issues/6),
  saga [#1](https://github.com/lbliii/orrery/issues/1),
  [#390](https://github.com/lbliii/orrery/issues/390) / [ADR 0010](./0010-aggregate-mcp-call-skill.md)
- **Depends on:** [0001](./0001-control-plane-wallet.md)

## Context

Orrery is Skill DNS + trust surfaces. Agents must **resolve** a name, then
**call the publisher MCP endpoint** directly. Orrery must not become a
reverse proxy that executes everyone’s tools.

Dogfood stars on this host (`html-to-pdf`, `world-time`) mount on the same
process for demo convenience. Product resolve records still advertise
publisher-shaped endpoints (`mcp://orrery.lol/s/…`) so the agent loop matches
production.

## Decision

1. **Resolve returns coordinates only** — endpoint, digest, key, price —
   never tool payloads.
2. **Call is always agent → publisher MCP** — aggregated `/mcp` on this
   host is not a product execution engine. Session-bound clients may use
   one `call_skill` **forwarder** on `/mcp` ([ADR 0010](./0010-aggregate-mcp-call-skill.md));
   publisher-direct mounts remain canonical. Orrery still does not host
   third-party tool execution.
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
  signing — no Orrery code path changes. Off-origin endpoints are **not**
  reached via `call_skill` (error `publisher_direct_required`).
- Default `/mcp` may list exactly one execution proxy (`call_skill`) so
  single-URL clients can complete gaze → resolve → call → seal without a
  tool zoo ([ADR 0010](./0010-aggregate-mcp-call-skill.md)).

## Links

- Saga: https://github.com/lbliii/orrery/issues/1
- Epic: https://github.com/lbliii/orrery/issues/6
- Aggregate proxy: [0010-aggregate-mcp-call-skill.md](./0010-aggregate-mcp-call-skill.md)
