# Design: Slim discovery MCP (default install)

- **Status:** Accepted (planner freeze)
- **Date:** 2026-08-11 (amended 2026-08-14: `call_skill` exception)
- **Design issue:** [#301](https://github.com/lbliii/orrery/issues/301),
  [#390](https://github.com/lbliii/orrery/issues/390)
- **Parent epic:** [#300](https://github.com/lbliii/orrery/issues/300)
- **Parent saga:** [#56](https://github.com/lbliii/orrery/issues/56) /
  tree-handling [#237](https://github.com/lbliii/orrery/issues/237)
- **Binds:** ADR 0004 (publisher-direct), ADR 0005 (thin harness),
  ADR 0010 (`call_skill` same-origin forwarder)

## Question frozen

What is the default Orrery MCP install surface so agents do not pay a flat tool
zoo on every session?

## Decision

Adopt **slim `/mcp` in place** (option 2). Option 3 (new `/mcp/gaze` URL) is
fallback only if in-place slim breaks external smoke beyond repair.

### Default allowlist (`tools/list` on advertised install)

- `gaze_match`, `gaze_search`, `gaze_describe`, `gaze_list_constellations`
- `resolve_name`
- `coverage_check`
- `explain_policy`
- **`call_skill`** — sole execution proxy ([ADR 0010](../adr/0010-aggregate-mcp-call-skill.md);
  design [#390](https://github.com/lbliii/orrery/issues/390)). Eight tools,
  not a catalog zoo.

### Explicitly not on default install

`convert`, `health`, `submit`, `result`, `fetch`, `get`, `answer`, `observe`,
`diff`, `source_watch_answer`, `run`, `status`, `continue_run`, `cancel`,
`rate`, `star_rate`, and any future star **call** aliases. Those names stay
off `tools/list`; `run` / `continue_run` / `cancel` / `status` are reached
only as `call_skill.tool` values.

### Dogfood / demo

Prefer **direct star/constellation MCP mounts** for call demos. If an aggregate
call zoo is retained for humans, mount it at a clearly labeled path
(e.g. `/mcp/dogfood`) that is **not** referenced by `/connect` Cursor snippet
or server-card `transport.endpoint`.

### Copy contract

Server card `description`, `/connect`, and `llms.txt` must state that `/mcp`
is gaze/resolve (shelf + Skill DNS) **plus one `call_skill` proxy**, and that
publisher-direct mounts remain canonical (ADR 0004 / 0010).

### ADR

[ADR 0010](../adr/0010-aggregate-mcp-call-skill.md) freezes `call_skill`.
ADR 0004 / 0005 consequences note the same-origin forwarder exception. No
second public MCP URL (`/mcp/call`) unless in-place allowlist tests cannot
be repaired.

## What leaves may assume

- Default advertised endpoint’s `tools/list` equals this allowlist (set equality
  or allowlist + denylist assertion) — **eight** names, including `call_skill`.
- `/connect` Cursor JSON points at that discovery endpoint.
- `discovery.MCP_TOOLS` / server card `tools[]` stay in sync.
- Megafile edits serialize: `discovery.py`, `dogfood.py`, connect page /
  `app.py` mount wiring.
