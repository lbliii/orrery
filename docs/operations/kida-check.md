# Kida Check

`orrery/kida-check` statically validates caller-supplied Kida template bundles
and returns coded findings in a signed Envelope. Pure sensor: `allowed_egress =
[]`, no render, no egress.

## Inputs

| Field | Required | Default | Notes |
| --- | --- | --- | --- |
| `templates[]` | yes | — | `{path, content}` — paths must end in `.html` or `.kida` |
| `validate_calls` | no | `true` | Validate `{% def %}` call sites (K-CMP-* codes) |
| `strict` | no | `false` | Fail on unified `{% end %}` closers |

## Finding codes (v1)

When `validate_calls` is enabled, component call-site mismatches emit stable
Kida codes such as:

| Code | Meaning |
| --- | --- |
| `K-CMP-001` | Unknown or missing component parameters |
| `K-CMP-002` | Literal argument type mismatch |

Additional syntax and load failures use other Kida diagnostic codes in the
same `findings[]` shape.

## Outputs

| Field | Meaning |
| --- | --- |
| `findings[]` | Diagnostic objects (`code`, `path`, `message`, `severity`, …) |
| `finding_codes` | Sorted unique codes |
| `template_count` | Templates validated in the bundle |
| `passed` | `true` when Kida check reports no problems |
| `validate_calls` / `strict` | Echo of flags used for the run |

## Direct MCP

`POST /stars/kida-check/mcp` — tool `check`.

## Ops

- No egress.
- Publisher key env: `ORRERY_KIDA_CHECK_KEY_ID` (or shared `ORRERY_STAR_*`).
- Dependency: `kida-templates` (PyPI) on the host.
- Acceptance: `uv run pytest tests/stars/test_kida_check.py -q`

## Demo corpus

Publish corpus uses the Kida README badge typo story (`lable` / wrong `count`
type) and expects `K-CMP-001` and `K-CMP-002` when `validate_calls` is true.
