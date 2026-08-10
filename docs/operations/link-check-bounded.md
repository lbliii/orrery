# Link Check Bounded

`orrery/link-check-bounded` extracts HTTPS links from a caller markdown/html
bundle, fails loud when the count exceeds `max_link_count`, and issues HEAD
requests only to allowlisted origins. Different SKU from `orrery/http-head`
(named targets). No model inference.

## Inputs

| Field | Required | Notes |
| --- | --- | --- |
| `files[]` | yes | `{path, content, format?}` — format `markdown` (default) or `html` |
| `max_link_count` | yes | 1..50; fail loud when extracted links exceed this |

## Outputs

| Field | Meaning |
| --- | --- |
| `links[]` | Per-link `{path, url, status, ...}` |
| `link_count` / `max_link_count` | Counts |
| `passed` | All link statuses are `ok` |
| `error` | `link_count_exceeded` when over cap (no egress attempted) |

Statuses: `ok`, `not_allowed`, `unreachable`, `redirect_not_allowed`.

## Egress

Allowlist (also in `star.toml`):

- `https://example.com`
- `https://docs.python.org`

Redirects that leave these HTTPS hosts fail loud. Cap: never check more than
`max_link_count` links (over-cap returns before any network call).

## Direct MCP

`POST /stars/link-check-bounded/mcp` — tool `check`.

## Ops

- Publisher key env: `ORRERY_LINK_CHECK_BOUNDED_KEY_ID` (or shared `ORRERY_STAR_*`).
- Acceptance: `uv run pytest tests/stars/test_link_check_bounded.py -q`
