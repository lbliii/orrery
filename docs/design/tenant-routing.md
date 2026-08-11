# Design: Tenant routing (path vs subdomain)

- **Status:** Accepted (planner freeze)
- **Date:** 2026-08-11
- **Design issue:** [#28](https://github.com/lbliii/orrery/issues/28)
- **Parent epic:** [#7](https://github.com/lbliii/orrery/issues/7) / [#60](https://github.com/lbliii/orrery/issues/60)
- **Binds:** ADR 0005 (namespaces as taxonomy)

## Question frozen

For MVP namespace tenancy on Railway, do we route tenants by **subdomain**
(`mcp://acme.orrery.dev/…`) or by **path / name prefix** (`acme/*` in Skill DNS
and gaze nodes)?

## Options

1. **Subdomain per tenant** — clean host isolation; needs wildcard DNS + TLS on
   Railway; heavier ops before private sky volume justifies it.
2. **Path / name-prefix tenancy** — `acme/*` star names + gaze `node` already
   model public vs namespace sky; no extra DNS for MVP.

## Decision

Adopt **option 2 (path / name-prefix)** for MVP.

- Canonical identity stays Skill DNS names (`acme/launch-gate`, `orrery/world-time`).
- Gaze nodes bind discovery to `public` vs a namespace id (e.g. `acme`) without
  requiring `acme.orrery.dev`.
- Direct MCP paths remain host-relative (`/stars/…/mcp`); namespace is in the
  **name**, not the hostname.
- Document Railway/DNS: single app host is enough for MVP; wildcard subdomain is
  **Not now** until private-sky volume or custom domains demand it.

## Consequences

- [#70](https://github.com/lbliii/orrery/issues/70) may implement gaze
  match/search scoping against the active node / namespace prefix.
- [#29](https://github.com/lbliii/orrery/issues/29) provisioning stays blocked
  on product UX; routing model is no longer the blocker for #70.
- Subdomain routing would require a new design + ADR amend — do not invent in a leaf.

## ADR

No new ADR — records MVP choice for #28; ADR 0005 namespace layer unchanged.
