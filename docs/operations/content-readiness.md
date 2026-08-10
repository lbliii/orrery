# Content Readiness

`orrery/content-readiness` is a **synchronous** constellation (ADR 0007
Example 1): a frozen planner subgraph over protocol stars that seals a
composite disposition `ready | needs-work | inconclusive`.

`pause_policy.allowed` is **false**. There is no write-authority or patch
stage. The terminal composite seal is in-package (no `orrery/artifact-seal`
star).

## Stages

1. `orrery/manifest-bind` — digest inventory derived from caller content
2. `orrery/manifest-preflight` — named policy check (default `orrery/docs-only@v1`)
3. `orrery/structure-audit` — markdown structure findings
4. `orrery/link-check-bounded` — allowlisted HTTPS HEAD under `max_link_count`
5. composite seal — disposition + stage evidence (in-package)

## Demo path (bundle in → composite envelope out)

```python
from stars.content_readiness.service import run

bundle = [
    {
        "path": "docs/readme.md",
        "content": (
            "---\ntitle: Readme\n---\n\n# Readme\n\n"
            "See [Python](https://docs.python.org/3/).\n"
        ),
    }
]

result = run(
    bundle,
    policy="orrery/docs-only@v1",
    max_link_count=20,
    link_transport=lambda url, *, timeout: (url, 200),  # fixture; live uses HEAD
)
assert result["disposition"] in {"ready", "needs-work", "inconclusive"}
assert result["chain"] == "signed-envelope-chain"
assert "stages" in result and "policy_digest" in result
```

Direct MCP: `POST /constellations/content-readiness/mcp` — tool `run`.

## Inputs

| Field | Required | Notes |
| --- | --- | --- |
| `files[]` | yes | `{path, content, format?}` — Orrery never opens a repo |
| `policy` | no | `orrery/docs-only@v1` (default) or `orrery/max-100-files@v1` |
| `max_link_count` | no | 1..50; default 20 |

## Dispositions

| Value | Meaning |
| --- | --- |
| `ready` | Preflight, structure, and bounded links all passed |
| `needs-work` | Stages completed with evaluative failures |
| `inconclusive` | Hard error / incomplete assessment |

## Ops

- Egress only via `link-check-bounded` allowlist (`example.com`, `docs.python.org`).
- Publisher key env: `ORRERY_CONTENT_READINESS_KEY_ID` (or shared `ORRERY_STAR_*`).
- Lease rule: `waiting_never_holds_worker_lease` (sync path never waits).
- Acceptance: `uv run pytest tests/stars/test_content_readiness.py -q`
