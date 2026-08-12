# Write Authority Check

`orrery/write-authority-check` verifies that an explicit write grant covers the
paths intended to change. Callers pass a `manifest_digest` (opaque, typically
from `orrery/manifest-bind`) plus an authority record. The star is pure: no
egress and no model inference.

## Inputs

| Field | Required | Notes |
| --- | --- | --- |
| `manifest_digest` | yes | 64-char lowercase hex |
| `authority.policy` | yes | `orrery/explicit-paths@v1` |
| `authority.allowed_paths[]` | yes | Relative paths under grant |
| `authority.grant_digest` | yes | Digest of `{policy, allowed_paths}` |
| `authority.witness` | no | Signed Envelope wire object (v1) |
| `authority.witness_public_key` | if witness | 64-char hex Ed25519 public key |

`grant_digest` is lowercase hex sha256 of canonical JSON
`{"allowed_paths":[<sorted>],"policy":"<policy>"}` (sorted keys, compact
separators).

## Witness envelope (v1)

Optional `witness` is a Chirp Envelope wire dict:

| Field | Meaning |
| --- | --- |
| `payload` | Must include `grant_digest` (hex sha256) and `allowed_paths` (string array) |
| `skill`, `version`, `tool`, `nonce`, `input_digest` | Envelope identity |
| `signature`, `key_id`, `alg` | Ed25519 signature (`alg` defaults to `Ed25519`) |

Verification rules:

1. Rebuild the Envelope and verify the signature with `witness_public_key`.
2. Require `payload.grant_digest` to equal the recomputed grant digest.
3. Require `payload.allowed_paths` to cover **exactly** `authority.allowed_paths`
   (set equality — no multi-party ceremony in v1).
4. `#224` boundary MCP consumes this same witness shape; do not invent alternates.

## Outputs

| Field | Meaning |
| --- | --- |
| `authorized` | `true` when no denial codes |
| `codes` | Denial / mismatch codes (empty when authorized) |
| `findings` | When denied, coded finding objects with advisory `remediation` |
| `grant_digest` | Recomputed digest |
| `witness_verified` | `true` only when a witness was supplied and fully verified |

## Direct MCP

`POST /stars/write-authority-check/mcp` — tool `check`.

## Ops

- No egress; pure check over caller digests and optional witness bytes.
- Publisher key env: `ORRERY_WRITE_AUTHORITY_CHECK_KEY_ID` (or shared `ORRERY_STAR_*`).
- Acceptance: `uv run pytest tests/stars/test_write_authority_check.py -q`
