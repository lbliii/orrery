# ADR 0010: Aggregate MCP `call_skill` proxy

- **Status:** Accepted
- **Date:** 2026-08-14
- **Issues:** design [#390](https://github.com/lbliii/orrery/issues/390),
  saga [#237](https://github.com/lbliii/orrery/issues/237),
  slim discovery [#301](https://github.com/lbliii/orrery/issues/301) /
  [#300](https://github.com/lbliii/orrery/issues/300)
- **Depends on:** [0004](./0004-publisher-direct-call.md),
  [0005](./0005-discovery-and-dual-trust.md)
- **Design note:** [slim-discovery-mcp.md](../design/slim-discovery-mcp.md)

## Context

Default advertised `/mcp` is discovery-only (seven gaze/resolve tools). Call
tools live on publisher mounts (`/stars/*/mcp`, `/constellations/*/mcp`). That
honors ADR 0004, but single-session MCP clients (Cursor default install) mount
**one** URL and cannot add ~45 publisher endpoints after `resolve_name`.

The 2026-08-12 end-to-end session completed gaze + resolve on `/mcp`, then had
to leave MCP (Python/curl) to execute. `/mcp/dogfood` already mounts a teaching
zoo; public callers have no equivalent without exploding `tools/list`.

ADR 0005 **Not now** still forbids *proxy-all-calls* (Orrery as FaaS / reverse
proxy for everyone’s tools). This ADR adds a **narrow same-origin forwarder**,
not a reversal.

## Decision

Adopt **option 3** from [#390](https://github.com/lbliii/orrery/issues/390):
one proxy tool on advertised `/mcp`. Do **not** add a second public URL
(`/mcp/call`) unless in-place allowlist tests cannot be repaired.

### 1. Tool name and inputs

Default `tools/list` gains exactly one execution proxy: **`call_skill`**.

| Input | Required | Meaning |
| --- | --- | --- |
| `name` | yes | Skill DNS (`orrery/stale-proof`, …) |
| `tool` | yes | Publisher tool (`run`, `fetch`, `continue_run`, …) |
| `arguments` | no | JSON object; default `{}` |

### 2. Forward, do not execute

`call_skill` **resolves** `name`, then issues `tools/call` on that record’s
**same-origin** publisher MCP with `tool` + `arguments`. Observable result
matches calling the publisher mount directly.

Implementation may loopback HTTP or dispatch in-process to the existing direct
MCP registry. It must **not** reimplement star/constellation business logic
in the aggregate, and must **not** register publisher call aliases
(`run`, `convert`, `fetch`, …) on default `tools/list` (denylist unchanged).

### 3. Same-origin public catalog only

v1 forwards only when the resolve endpoint is this Orrery origin (public sky
stars and constellations already mounted here). Off-origin / third-party
publisher URLs return structured error `publisher_direct_required` — the
client must call that publisher MCP itself (ADR 0004 remains canonical).

Unknown `name` → `not_found`. Unknown publisher `tool` → `unknown_tool`.
Allowlist-gated stars keep publisher enforcement; `call_skill` is not a
coverage bypass. No new rate-limit or `tool_context_budget` quota in v1
(inherit host MCP limits; do not expand `tools/list`).

`continue_run`, `cancel`, and `status` are reachable **only** as `tool`
values on `call_skill`, not as top-level aggregate tools.

### 4. Slim allowlist stays thin

Default advertised install is **ten** tools (eight from this ADR plus
`index_ping` / `rate_listing` from [ADR 0012](./0012-opt-in-listing.md)):

- `gaze_match`, `gaze_search`, `gaze_describe`, `gaze_list_constellations`
- `resolve_name`, `coverage_check`, `explain_policy`
- **`call_skill`**
- **`index_ping`**, **`rate_listing`** (opt-in newcomer shelf; ADR 0012)

`/mcp/dogfood` and direct mounts are unchanged and stay off `/connect`.

### 5. MCP `content[].text` is JSON

`call_skill` returns JSON text (not Python `Envelope(...)` repr):

```json
{
  "status": "ok",
  "skill": "orrery/stale-proof",
  "tool": "run",
  "payload": {},
  "envelope_wire": {}
}
```

On failure: `"status": "error"` plus `"error": {"code": "...", "message": "..."}`.
`payload` is the Envelope payload when the publisher returns a signed
Envelope; `envelope_wire` is `Envelope.to_wire()` so verify still works.
Pause/resume fields stay inside `payload` until leaf [#394](https://github.com/lbliii/orrery/issues/394).

The same JSON envelope (`status`, `payload`, optional `envelope_wire`) is
the contract sibling leaf [#391](https://github.com/lbliii/orrery/issues/391)
applies to the other `/mcp` tools. `call_skill` must emit it from day one.

### 6. Copy

Server card, `/connect`, and `llms.txt` state that `/mcp` is gaze/resolve
**plus** one `call_skill` proxy, and that publisher-direct mounts remain
canonical (ADR 0004).

## Consequences

- Leaves may assume the advertised allowlist (ten tools after ADR 0012) and
  must not re-decide proxy vs zoo vs second URL.
- ADR 0004 call path stays publisher-direct; this host may **forward** for
  session-bound clients.
- ADR 0005 “proxy-all-calls” still forbids off-origin execution hosting.
- Cursor-class clients can complete gaze → resolve → call → seal on one MCP
  URL (e.g. `orrery/stale-proof` `run` `{}` → `fresh_proof`).

## Links

- Design: https://github.com/lbliii/orrery/issues/390
- Slim discovery: [slim-discovery-mcp.md](../design/slim-discovery-mcp.md)
- Publisher-direct: [0004-publisher-direct-call.md](./0004-publisher-direct-call.md)
- Thin harness: [0005-discovery-and-dual-trust.md](./0005-discovery-and-dual-trust.md)
