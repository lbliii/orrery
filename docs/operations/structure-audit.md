# Structure Audit

`orrery/structure-audit` scans a caller-supplied markdown file set for coded
structure findings. Pure transform: `allowed_egress = []`, no model inference.

## Inputs

| Field | Required | Notes |
| --- | --- | --- |
| `files[]` | yes | `{path, content}` — paths must end in `.md` |

## Finding codes

| Code | Meaning |
| --- | --- |
| `missing_h1` | No H1 / document does not start with H1 |
| `heading_level_skip` | Heading jumps more than one level |
| `frontmatter_invalid` | Malformed YAML frontmatter fence |
| `frontmatter_missing_title` | Frontmatter present without `title:` |
| `empty_file` | Empty content |
| `orphan_file` | No inbound relative `.md` links (index/readme exempt) |

Each finding also includes optional advisory `remediation` text (machine-oriented
fix hint). Remediation does not change codes or pass/fail.

## Outputs

| Field | Meaning |
| --- | --- |
| `findings[]` | Coded finding objects (`code`, `path`, `message`, `remediation`, …) |
| `finding_codes` | Sorted unique codes |
| `passed` | `true` when findings empty |

## Direct MCP

`POST /stars/structure-audit/mcp` — tool `audit`.

## Ops

- No egress.
- Publisher key env: `ORRERY_STRUCTURE_AUDIT_KEY_ID` (or shared `ORRERY_STAR_*`).
- Acceptance: `uv run pytest tests/stars/test_structure_audit.py -q`
