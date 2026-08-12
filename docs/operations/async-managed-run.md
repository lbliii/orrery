# Async managed run: submit → result

Managed CPU stars (`html-to-pdf`, `csv-report`, `image-transform`) expose an
async lane: **`submit`** enqueues work on the private worker and returns a
`run_id`; **`result(run_id)`** polls until the run is terminal and returns a
signed final receipt (or interim queued/running state).

Sync **`convert`** on `html-to-pdf` still renders in the API process for small
jobs when the caller can wait. Prefer `convert` for quick PDFs; use
`submit`/`result` for durable worker execution and artifact receipts.

## html-to-pdf curl sequence

Point at the star's direct MCP endpoint (ADR 0004 publisher-direct):

```bash
BASE="https://orrery.lol"
ENDPOINT="$BASE/stars/html-to-pdf/mcp"

# 1. Queue a managed PDF run — note run_id in the signed Envelope payload
curl -sS "$ENDPOINT" \
  -H 'Content-Type: application/json' \
  -H 'mcp-protocol-version: 2025-06-18' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{
        "name":"submit",
        "arguments":{"html":"<h1>Orrery</h1>","idempotency_key":"doc-1"}
      }}'

# 2. Poll by run_id until state is succeeded (or failed/cancelled)
RUN_ID="<run_id from submit>"
curl -sS "$ENDPOINT" \
  -H 'Content-Type: application/json' \
  -H 'mcp-protocol-version: 2025-06-18' \
  -d "{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/call\",\"params\":{
        \"name\":\"result\",
        \"arguments\":{\"run_id\":\"$RUN_ID\"}
      }}"
```

While the worker has not finished, `result` returns `{run_id, state}` with
`state` of `queued` or `running`. When terminal, the Envelope payload includes
`receipt` (artifact id, digest, content type) and `terminal_reason`.

## Unknown run_id

Calling `result` with an unknown or inaccessible `run_id` returns a structured
payload `{error: "run_not_found", run_id}` inside the signed Envelope — not a
generic MCP `-32603` tool execution error.

Acceptance:

```bash
uv run pytest tests/stars/test_cpu_workloads.py tests/test_run_admission.py -q
```
