# Plan: Agent Plugins rim — pointer package + sealed conformance

- **Status:** Accepted (planner freeze)
- **Date:** 2026-08-17
- **Parent product saga:** [#1](https://github.com/lbliii/orrery/issues/1)
- **Complements:** [tree-handling-rim.md](./tree-handling-rim.md) (closed
  [#237](https://github.com/lbliii/orrery/issues/237) — do not reopen),
  [vending-machine-sky.md](./vending-machine-sky.md) (ADR 0005),
  [issue-lifecycle.md](./issue-lifecycle.md)
- **External spec:** [Agent Plugins 1.0.0](https://github.com/agentplugins/agent-plugins-spec/blob/main/spec/1.0.0.md)
- **ADRs cited:** [0004](../adr/0004-publisher-direct-call.md),
  [0005](../adr/0005-discovery-and-dual-trust.md),
  [0007](../adr/0007-constellation-subtree-contract.md),
  [0010](../adr/0010-aggregate-mcp-call-skill.md),
  [0012](../adr/0012-opt-in-listing.md)

## Why this matters

Agent Plugins 1.0.0 is a portable **directory package** for Agent Skills and
MCP servers. It does not define trust, signatures, a registry, a validator,
or an audit trail. Those holes are the tree-handling rim: gaze → resolve →
call → seal over caller bytes.

Without this freeze we would either become a plugin client (install / load /
exec — ADR 0004 / 0005) or a SKILL.md marketplace (ADR 0001 / 0012).

**Fix:** Ship Orrery as a **pointer** plugin (remote MCP only), then a
protocol star and constellation that hang a sealed Agent Plugins 1.0.0
receipt. Orrery does not install, load, or execute plugins.

## North star

A harness can **point** at Orrery via a portable plugin directory, and a
worker can **hang a sealed Agent Plugins 1.0.0 receipt** on its tree.

## Decisions (leaves may assume)

1. **Epic, not saga.** Too small; #237 already covered tree-handling.
2. **Pointer, not install.** Brand line stays “skills you point at, not
   install.” Official package is `plugin.json` + `mcp.json` with only
   `streamable-http` to `https://orrery.lol/mcp` (slim default, ADR 0010).
   No `skills/`, no stdio, no `PLUGIN_DATA`.
3. **New protocol star, not a `manifest-preflight` policy.**
   `manifest-preflight` only sees `{path, sha256, size}`. Plugin rules need
   file contents. Mirror `structure-audit` / `content-readiness`: caller
   bundle `{path, content}`; Orrery never opens a repo.
4. **Pin schemas in-repo.** Spec §5.2 / §7.2.1: clients MUST NOT fetch
   `$schema` while loading. Vendor schemas under
   `plugins/schemas/1.0.0/`. Do **not** add agent-plugins.org to
   `orrery/well-known`.
5. **Conformance ≠ listing.** `plugin-preflight` grades Agent Plugins
   1.0.0 (stdio is valid). The sky still requires HTTPS `streamable-http`
   (ADR 0012).
6. **`lol.orrery` is parked.** Extension + listing adapter needs its own
   design (likely ADR 0013). No leaves until a caller exists.

## Not now

- Plugin client / runtime (install, load, exec, `PLUGIN_DATA`)
- Marketplace of `SKILL.md` files
- Crawl of plugin repos
- Secrets / permission UX / sandbox
- Product-level “pick the plugin” (ADR 0005)
- Stuffing `/mcp` with new tools for this epic
- Expanding `orrery/well-known` to third-party specs

## GitHub issue map

Parent saga [#1](https://github.com/lbliii/orrery/issues/1). Epic
[#532](https://github.com/lbliii/orrery/issues/532).

| Kind | Issue | Gate |
| --- | --- | --- |
| Epic | [#532](https://github.com/lbliii/orrery/issues/532) Agent Plugins rim | `blocked` until children exit |
| Leaf | [#533](https://github.com/lbliii/orrery/issues/533) Official `orrery` plugin package | `ready` (wave 0; no design) |
| Design | [#534](https://github.com/lbliii/orrery/issues/534) `plugin-preflight` contract | planner; blocks #535 |
| Leaf | [#535](https://github.com/lbliii/orrery/issues/535) `orrery/plugin-preflight` star | `blocked` on #534 |
| Leaf | [#536](https://github.com/lbliii/orrery/issues/536) `orrery/plugin-readiness` constellation | `blocked` on #535 |
| Design | [#537](https://github.com/lbliii/orrery/issues/537) `lol.orrery` listing pointer | parked / `blocked` |

## Exit criteria

1. Wave 0 package CI-valid against vendored schemas (no network).
2. `orrery/plugin-preflight` L0 + L1 per
   [star-eval](../design/star-eval.md).
3. `orrery/plugin-readiness` publishes `subtree_contract` (ADR 0007).
4. This page is linked from
   [tree-handling-rim](./tree-handling-rim.md) follow-ons.
5. Docs state we are not a plugin client.

## Success signal

A planner cites a plugin-readiness digest; a worker hangs a
plugin-preflight envelope; a client points at Orrery by loading
`plugins/orrery/` — without Orrery launching a plugin process.
