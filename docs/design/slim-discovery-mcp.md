# Design: Slim discovery MCP (default install)

- **Status:** Accepted (planner freeze)
- **Date:** 2026-08-11
- **Design issue:** [#301](https://github.com/lbliii/orrery/issues/301)
- **Parent epic:** [#300](https://github.com/lbliii/orrery/issues/300)
- **Parent saga:** [#56](https://github.com/lbliii/orrery/issues/56)
- **Binds:** ADR 0004 (publisher-direct), ADR 0005 (thin harness)

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

### Explicitly not on default install

`convert`, `health`, `submit`, `result`, `fetch`, `get`, `answer`, `observe`,
`diff`, `source_watch_answer`, `run`, `status`, `continue_run`, `cancel`,
`rate`, `star_rate`, and any future star **call** aliases.

### Dogfood / demo

Prefer **direct star/constellation MCP mounts** for call demos. If an aggregate
call zoo is retained for humans, mount it at a clearly labeled path
(e.g. `/mcp/dogfood`) that is **not** referenced by `/connect` Cursor snippet
or server-card `transport.endpoint`.

### Copy contract

Server card `description`, `/connect`, and `llms.txt` must state in one line:
*This MCP is gaze/resolve (shelf + Skill DNS). Call the resolved publisher
endpoint for execution.*

### ADR

Amend ADR 0004 / 0005 consequences lightly (“default aggregate is
discovery-only”). No new ADR; no durable second public MCP URL unless option 3
is forced later.

## What leaves may assume

- Default advertised endpoint’s `tools/list` equals this allowlist (set equality
  or allowlist + denylist assertion).
- `/connect` Cursor JSON points at that discovery endpoint.
- `discovery.MCP_TOOLS` / server card `tools[]` stay in sync.
- Megafile edits serialize: `discovery.py`, `dogfood.py`, connect page /
  `app.py` mount wiring.
