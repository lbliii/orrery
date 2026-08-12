# Table Fresh

`orrery/table-fresh` is a direct callable constellation. Call `run` with a
caller-held baseline `{rows, source_digest?}`; Orrery freshly fetches
`csv-url`'s bounded `flights-airport` sample (not `flights-sample`), converts
origin/destination to a deterministic route key, and invokes `table-diff`. It
retains no baseline. The verdict is explicitly limited to the current 100-row
sample and carries both source and independently computed snapshot digests.

Each baseline row must have **exactly** `{origin, destination, count}` — three-letter
airport codes and a non-negative integer count. Do not pass `dataset`; that field
belongs to `orrery/csv-url`.

## Copy-paste baseline (MCP `run`)

Direct MCP: `POST /constellations/table-fresh/mcp` — tool `run`.

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "run",
    "arguments": {
      "baseline": {
        "rows": [
          {"origin": "ABE", "destination": "ATL", "count": 853},
          {"origin": "ABE", "destination": "BHM", "count": 1}
        ],
        "source_digest": "sha256:prior"
      }
    }
  }
}
```

Invalid baselines (wrong keys, missing `rows`, or `dataset` instead of rows)
return `invalid_baseline` with remediation text, `expected_shape`, and this
example — not a bare error code.
