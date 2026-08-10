# Ship Check / Content Ship Check

`orrery/ship-check` (content-ship-check evolution) is a **synchronous**
constellation (ADR 0007): one composite receipt, two modes selected via run
input. `pause_policy.allowed` is **false**. It never authorizes deployment.

## Modes

| `mode` | Default | Inputs | Stages |
| --- | --- | --- | --- |
| `metadata` | yes | `package*` + optional `source_digest` | release → source-watch → world-time → artifact-seal |
| `content-bundle` | no | `files*` (+ optional `policy`, `max_link_count`) | content-readiness vocabulary: manifest-bind → manifest-preflight → structure-audit → link-check-bounded → artifact-seal |

Mode-specific stages are marked `optional: true` on the agent-card
`subtree_contract`; the terminal `artifact-seal` composite is always present.

## Metadata mode (backward compatible)

Combines named PyPI/npm release metadata, fixed Python release-note change
evidence, and current UTC. Returns `verdict` `ready_to_reason` |
`incomplete` (plus composite `disposition` `ready` | `not-ready`). Supply a
prior source digest from an agent-held receipt for the source-watch comparison.

```python
from stars.ship_check.service import run

result = run(
    "httpx",
    "sha256:prior",
    package_provider=lambda _: {"version": "1"},
    source_provider=lambda _: {"status": "unchanged"},
    world_time_provider=lambda: {"datetime": "2026-01-01T00:00:00Z"},
)
assert result["mode"] == "metadata"
assert result["verdict"] == "ready_to_reason"
assert result["chain"] == "signed-envelope-chain"
```

## Content-bundle mode

Reuses the content-readiness stage pipeline over a caller-supplied content
bundle. Orrery never opens a repository. Dispositions:
`ready | needs-work | inconclusive`.

```python
from stars.ship_check.service import run

bundle = [
    {
        "path": "docs/readme.md",
        "content": "---\ntitle: Readme\n---\n\n# Readme\n\nHello.\n",
    }
]
result = run(mode="content-bundle", files=bundle)
assert result["disposition"] in {"ready", "needs-work", "inconclusive"}
assert "manifest-bind" in result["stages"]
```

Direct MCP: `POST /constellations/ship-check/mcp` — tool `run`.

## Ops

- Metadata egress: PyPI, npm, docs.python.org (source-watch).
- Content-bundle egress: link-check-bounded allowlist (`example.com`,
  `docs.python.org`).
- Publisher key env: `ORRERY_SHIP_CHECK_KEY_ID` (or shared `ORRERY_STAR_*`).
- Lease rule: `waiting_never_holds_worker_lease`.
- Acceptance: `uv run pytest tests/stars/test_ship_check.py -q`
