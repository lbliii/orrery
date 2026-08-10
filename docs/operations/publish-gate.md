# Publish Gate

`orrery/publish-gate` is the **publication-authority seam** constellation: it
proves the two-phase edit/publish model after
`orrery/authorized-content-patch` without Orrery performing git push or pages
deploy.

Pipeline: prior artifact envelope → publish-profile `write-authority-check` →
optional human witness → release seal.

`pause_policy.allowed` is **true** with mode `awaiting_witness` (ADR 0007).
Resume MCP (`continue_run`) is named on the card only — out of scope for v1.
Waiting never holds a worker lease.

## Two-phase model

1. **Edit** — `orrery/authorized-content-patch` seals `disposition=authorized`
   (readiness → edit write-authority → patch-capture).
2. **Publish** — this constellation consumes that prior envelope, checks a
   **distinct** publish authority profile (`authority.profile=publish`),
   optionally waits for a human witness, then seals `released`.

## Stages

1. `prior-artifact` — require a valid prior Chirp envelope from
   `orrery/authorized-content-patch` with `disposition=authorized`
2. `orrery/write-authority-check` — publish-profile grant over the prior
   manifest digest
3. `human-witness` — optional / required witness (role `witness`); may seal
   `awaiting_witness` when `require_witness=true` and no witness is present
4. composite release seal — disposition + stage evidence (in-package)

## Demo path (prior envelope + publish grant → release seal)

```python
from stars.publish_gate.service import run
from stars.write_authority_check.contract import POLICY_EXPLICIT_PATHS
from stars.write_authority_check.service import grant_digest

paths = ["docs/readme.md"]
authority = {
    "profile": "publish",
    "policy": POLICY_EXPLICIT_PATHS,
    "allowed_paths": paths,
    "grant_digest": grant_digest(POLICY_EXPLICIT_PATHS, paths),
}

result = run(
    prior_envelope,  # wire Envelope from authorized-content-patch
    authority,
    require_witness=False,
)
assert result["disposition"] in {
    "released",
    "denied",
    "awaiting_witness",
    "inconclusive",
}
assert result["two_phase"]["edit"] == "orrery/authorized-content-patch"
assert "no git push" in " ".join(result["limitations"]).lower() or any(
    "deploy" in item.lower() for item in result["limitations"]
)
```

Direct MCP: `POST /constellations/publish-gate/mcp` — tool `run`.

## Inputs

| Field | Required | Notes |
| --- | --- | --- |
| `prior_envelope` | yes | Chirp Envelope wire from authorized-content-patch |
| `authority` | yes | `profile=publish`, `policy`, `allowed_paths`, `grant_digest`, optional witness |
| `prior_public_key` | no | 64-char hex; when set, prior signature must verify |
| `require_witness` | no | default `false`; when `true` and no witness → `awaiting_witness` |

## Dispositions

| Value | Meaning |
| --- | --- |
| `released` | Prior ok, publish grant ok, witness satisfied/skipped |
| `denied` | Publish grant failed or witness invalid |
| `awaiting_witness` | Witness required and missing (`pause_policy` mode) |
| `inconclusive` | Hard error / invalid prior / profile |

## Ops

- No egress (authority seam + seal only).
- Publisher key env: `ORRERY_PUBLISH_GATE_KEY_ID` (or shared `ORRERY_STAR_*`).
- Lease rule: `waiting_never_holds_worker_lease`.
- Boundary: does **not** git push, deploy pages, or apply patches.
- Acceptance: `uv run pytest tests/stars/test_publish_gate.py -q`
