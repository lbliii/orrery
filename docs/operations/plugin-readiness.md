# Plugin Readiness

`orrery/plugin-readiness` is a **synchronous** constellation (ADR 0007):
a frozen planner subgraph that seals
`conformant | needs-work | inconclusive` over a caller plugin bundle.

`pause_policy.allowed` is **false**. Orrery does not install or launch
plugins. The terminal composite seal is in-package.

## Stages

1. `orrery/manifest-bind` — digest inventory derived from caller content
2. `orrery/plugin-preflight` — Agent Plugins 1.0.0 (`agent-plugins/1.0.0`)
3. `orrery/structure-audit` — only on discovered `skills/*/SKILL.md`
   (skipped when none)
4. composite seal — disposition + stage evidence (in-package)

## Demo path

```python
from pathlib import Path

from stars.plugin_readiness.service import run

root = Path("plugins/orrery")
bundle = [
    {"path": path.name, "content": path.read_text(encoding="utf-8")}
    for path in root.iterdir()
    if path.is_file()
]
result = run(bundle)
assert result["disposition"] == "conformant"
```

Direct MCP: `POST /constellations/plugin-readiness/mcp` — tool `run`.

## Dispositions

| Value | Meaning |
| --- | --- |
| `conformant` | Preflight passed; structure passed or skipped |
| `needs-work` | Stages completed with evaluative failures |
| `inconclusive` | Hard error / incomplete assessment |

## Ops

- No egress.
- Publisher key env: `ORRERY_PLUGIN_READINESS_KEY_ID` (or shared `ORRERY_STAR_*`).
- Lease rule: `waiting_never_holds_worker_lease`.
- Acceptance: `uv run pytest tests/stars/test_plugin_readiness.py -q`
