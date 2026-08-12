# Board Memo (resumable constellation)

`orrery/board-memo` is the **ADR 0007 Example 2** dogfood constellation: it
pauses for one typed audience/recommendation choice, resumes via
`continue_run`, and finishes with a verifiable PDF artifact plus composite
Envelope.

Pipeline: memo-bind → audience-choice pause → pdf-seal composite.

`pause_policy.allowed` is **true** with mode `awaiting_input`. Waiting never
holds a worker, MCP, or HTTP lease.

## Stages

1. `memo-bind` — validate title + summary input bundle
2. `audience-choice` — durable pause with exactly one `action_request`
3. `pdf-seal` — render memo HTML via `orrery/html-to-pdf` and seal composite

## Demo path (start → status → continue → PDF)

```python
from stars.board_memo.service import continue_run, run, status

started = run(
    "Q3 Platform Update",
    "Revenue grew 12% with stable infra costs.",
    author="ops",
    caller_id="demo-client",
    private_key=...,  # Ed25519 signing key
)
assert started["disposition"] == "awaiting_input"
assert len(started["outstanding_action_requests"]) == 1
assert started["lease_held"] is False

request_id = started["outstanding_action_requests"][0]["request_id"]
paused = status(started["run_id"])
assert len(paused["outstanding_action_requests"]) == 1

completed = continue_run(
    started["run_id"],
    request_id,
    {"audience": "board", "recommendation": "approve"},
    caller_id="demo-client",
    private_key=...,
)
assert completed["disposition"] == "completed"
assert completed["artifact_digest"]
```

Direct MCP: `POST /constellations/board-memo/mcp` — tools
`run`, `status`, `continue_run`, `cancel`.

## MCP sequence (run → continue_run → terminal)

Copy-paste against `POST /constellations/board-memo/mcp` (Streamable HTTP JSON-RPC).

**1. Start run** — expect `disposition: awaiting_input`, `graph_position: audience-choice`:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "run",
    "arguments": {
      "title": "Q3 Platform Update",
      "summary": "Revenue grew 12% with stable infra costs.",
      "author": "ops",
      "caller_id": "demo-client"
    }
  }
}
```

**2. Continue at `audience-choice`** — use `run_id` and
`outstanding_action_requests[0].request_id` from step 1; terminal `disposition: completed`:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "continue_run",
    "arguments": {
      "run_id": "<run_id>",
      "request_id": "<request_id>",
      "response": {"audience": "board", "recommendation": "approve"},
      "caller_id": "demo-client"
    }
  }
}
```

Also surfaced on the Agent Card `run_contract.continue_shapes` and via
`explain_policy` (`mcp_sequence`, `continue_shapes`) for `orrery/board-memo`.

## Inputs

| Field | Required | Notes |
| --- | --- | --- |
| `title` | yes | Memo title |
| `summary` | yes | Memo body text |
| `author` | no | Author label embedded in PDF |
| `caller_id` | no | Resume identity (default `anonymous`) |

## Continue response schema

| Field | Values |
| --- | --- |
| `audience` | `board`, `executive`, `investor` |
| `recommendation` | `approve`, `revise`, `defer` |

## Dispositions

| Value | Meaning |
| --- | --- |
| `awaiting_input` | Paused at audience-choice with one outstanding request |
| `completed` | PDF artifact sealed; composite receipt available |
| `cancelled` | Authenticated cancel |
| `expired` | `action_request.expires_at` passed |
| `inconclusive` | Invalid start input |

## Idempotency

Duplicate `continue_run` with the same
`(caller_id, run_id, request_id, payload_digest)` replays the same composite
and artifact digest — no second PDF is minted.

## Ops

- Checkpoint store: in-memory `ConstellationRunStore` (design #152).
- Publisher key env: `ORRERY_BOARD_MEMO_KEY_ID` (or shared `ORRERY_STAR_*`).
- Lease rule: `waiting_never_holds_worker_lease`.
- Acceptance: `uv run pytest tests/test_constellation_run.py tests/stars/test_board_memo.py -q`
