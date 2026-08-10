# Authorized Content Patch

`orrery/authorized-content-patch` is a **synchronous** constellation: a frozen
planner subgraph that proves multi-step governed content work without Orrery
applying patches to the caller filesystem.

Pipeline: readiness gates (content-readiness reuse) →
`write-authority-check` → `patch-capture` → composite seal.

`pause_policy.allowed` is **false**. Publication / deploy belongs to
`orrery/publish-gate` (#216), not this SKU.

## Stages

1. Readiness gates via `orrery/content-readiness` vocabulary:
   `manifest-bind` → `manifest-preflight` → `structure-audit` →
   `link-check-bounded`
2. `orrery/write-authority-check` — explicit grant over the after manifest
3. `orrery/patch-capture` — before/after sealed patch digest (no apply)
4. composite seal — disposition + stage evidence (in-package)

## Demo path (bundles + grant in → composite envelope out)

```python
from stars.authorized_content_patch.service import run
from stars.write_authority_check.contract import POLICY_EXPLICIT_PATHS
from stars.write_authority_check.service import grant_digest

before = [
    {
        "path": "docs/readme.md",
        "content": "---\ntitle: Readme\n---\n\n# Readme\n\nHello.\n",
    }
]
after = [
    {
        "path": "docs/readme.md",
        "content": (
            "---\ntitle: Readme\n---\n\n# Readme\n\n"
            "See [Python](https://docs.python.org/3/).\n"
        ),
    }
]
paths = ["docs/readme.md"]
authority = {
    "policy": POLICY_EXPLICIT_PATHS,
    "allowed_paths": paths,
    "grant_digest": grant_digest(POLICY_EXPLICIT_PATHS, paths),
}

result = run(
    before,
    after,
    authority,
    policy="orrery/docs-only@v1",
    max_link_count=20,
    link_transport=lambda url, *, timeout: (url, 200),
)
assert result["disposition"] in {
    "authorized",
    "denied",
    "needs-work",
    "inconclusive",
}
assert result["chain"] == "signed-envelope-chain"
assert "Does not apply patches" in " ".join(result["limitations"])
```

Direct MCP: `POST /constellations/authorized-content-patch/mcp` — tool `run`.

## Inputs

| Field | Required | Notes |
| --- | --- | --- |
| `before[]` | yes | `{path, content, format?}` — may be empty (all-new) |
| `after[]` | yes | `{path, content, format?}` — assessed for readiness |
| `authority` | yes | `policy`, `allowed_paths`, `grant_digest`, optional witness |
| `policy` | no | `orrery/docs-only@v1` (default) or `orrery/max-100-files@v1` |
| `max_link_count` | no | 1..50; default 20 |

## Dispositions

| Value | Meaning |
| --- | --- |
| `authorized` | Readiness ready, grant ok, patch captured, changed paths ⊆ grant |
| `denied` | Write grant failed or changed paths outside grant |
| `needs-work` | Readiness completed with evaluative failures |
| `inconclusive` | Hard error / incomplete assessment |

## Ops

- Egress only via readiness `link-check-bounded` allowlist.
- Publisher key env: `ORRERY_AUTHORIZED_CONTENT_PATCH_KEY_ID` (or shared
  `ORRERY_STAR_*`).
- Lease rule: `waiting_never_holds_worker_lease` (sync path never waits).
- Boundary: does **not** apply patches to your filesystem.
- Acceptance: `uv run pytest tests/stars/test_authorized_content_patch.py -q`
