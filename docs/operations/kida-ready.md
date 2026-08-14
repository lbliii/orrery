# Kida Ready

`orrery/kida-ready` is a **synchronous** constellation (ADR 0007): a frozen
planner subgraph that runs **kida-check → gate → kida-render → composite seal**
with disposition **`ready | needs-work | inconclusive`**.

`pause_policy.allowed` is **false**. Render runs only when static check passes
the internal gate. The terminal composite seal is in-package (no
`orrery/artifact-seal` star).

## Stages

1. `orrery/kida-check` — static Kida findings over caller template bundle
2. `gate` — blocks render when check fails
3. `orrery/kida-render` — HTML + `template_digest`, `data_digest`, `output_digest`
4. composite seal — disposition + stage evidence (in-package)

## Demo path (templates + data in → composite envelope out)

```python
from stars.kida_ready.service import run

templates = [
    {
        "path": "templates/dashboard.html",
        "content": (
            '{% def badge(count: int, label: str) %}\n'
            '<span class="badge">{{ count }} {{ label }}</span>\n'
            '{% enddef %}\n\n'
            '{{ badge(count=count, label=label) }}\n'
        ),
    }
]
data = {"count": 5, "label": "Messages"}

result = run(templates, data)
assert result["disposition"] in {"ready", "needs-work", "inconclusive"}
assert result["chain"] == "signed-envelope-chain"
assert "stages" in result and "policy_digest" in result
```

Direct MCP: `POST /constellations/kida-ready/mcp` — tool `run`.

## Inputs

| Field | Required | Notes |
| --- | --- | --- |
| `templates[]` | yes | `{path, content}` — same bundle shape as kida-check |
| `data` | yes | JSON object forwarded to kida-render |
| `validate_calls` | no | default true |
| `strict` | no | default false |
| `surface` | no | `html` only in v1 |

## Dispositions

| Value | Meaning |
| --- | --- |
| `ready` | Check passed, gate open, render succeeded with digests |
| `needs-work` | Check completed with findings — render skipped |
| `inconclusive` | Hard error (invalid bundle, render failure, etc.) |

## Ops

- Egress: none (both member stars are in-memory).
- Publisher key env: `ORRERY_KIDA_READY_KEY_ID` (or shared `ORRERY_STAR_*`).
- Lease rule: `waiting_never_holds_worker_lease` (sync path never waits).
- Acceptance: `uv run pytest tests/stars/test_kida_ready.py -q`
