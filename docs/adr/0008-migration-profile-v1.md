# ADR 0008: MigrationProfile v1 (pinned targets + receipt contract)

- **Status:** Accepted
- **Date:** 2026-08-10
- **Issues:** [#165](https://github.com/lbliii/orrery/issues/165),
  epic [#161](https://github.com/lbliii/orrery/issues/161),
  saga [#160](https://github.com/lbliii/orrery/issues/160)
- **Depends on:** [0004](./0004-publisher-direct-call.md),
  [0005](./0005-discovery-and-dual-trust.md),
  [0006](./0006-decision-receipt.md),
  [0007](./0007-constellation-subtree-contract.md)
- **Complements:** [envelope-verification.md](../verification/envelope-verification.md)

## Context

Saga [#160](https://github.com/lbliii/orrery/issues/160) wants named, pinned
migration callables: analyze → plan → explicit apply → validate → sealed
receipt. Without a shared profile schema, MyST→MDX and OpenAPI upgrade each
invent side-channel fields, floating `latest` targets sneak into receipts, and
a standalone verifier cannot recover exact target/profile/tool versions.

Epic [#161](https://github.com/lbliii/orrery/issues/161) requires one
`MigrationProfile` contract that two independently implemented profiles share.
Design [#165](https://github.com/lbliii/orrery/issues/165) freezes that
contract **before** any converter ships.

## Decision

### 1. Profile document (required fields)

A MigrationProfile is a versioned JSON object. Every public profile MUST include
exactly these top-level fields (no profile-specific sibling keys at the root;
extensions live only under `feature_vocabulary` and `compatibility_policy`
as defined below).

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `schema_version` | string | yes | Always `"migration-profile/v1"` for this ADR |
| `profile_id` | string | yes | Stable kebab id, e.g. `docs/myst-to-mdx-baseline` |
| `version` | string | yes | SemVer of **this profile document** (`MAJOR.MINOR.PATCH`) |
| `source` | object | yes | `{ "kind": "<string>", "version": "<pinned>" }` |
| `target` | object | yes | `{ "kind": "<string>", "version": "<pinned>" }` — never `latest` |
| `feature_vocabulary` | object | yes | `{ "supported": [...], "unsupported": [...] }` |
| `compatibility_policy` | object | yes | Named policy + severity vocabulary (below) |
| `execution_locality` | string | yes | One of `agent_local`, `creator_owned_tooling`, `orrery_coord_only` |
| `transformer` | object | yes | Tool identity (below) |
| `validator` | object | yes | Tool identity (below) |
| `retention_redaction` | object | yes | Default retention/redaction policy (below) |
| `profile_digest` | string | yes | Lowercase hex `sha256` of canonical profile bytes **excluding** this field |

Optional (non-side-channel) metadata only:

| Field | Type | Meaning |
| --- | --- | --- |
| `title` | string | Human label |
| `description` | string | ≤2 KiB UTF-8 |
| `supersedes` | string | Prior `profile_id@version` this replaces |

Root keys outside this table are **forbidden** in v1. Profile-specific
semantics belong in `feature_vocabulary` entries and
`compatibility_policy.rules[]`, not new top-level keys.

### 2. Kind / version pinning

`source.kind` and `target.kind` are opaque strings from a small shared set for
v1 examples:

| kind | Typical version pin |
| --- | --- |
| `myst-markdown` | e.g. `myst-md@1.x` dialect pin recorded as `1.3.0` |
| `mdx` | e.g. `mdx@3.0.0` (MDX baseline; site adapters are separate profiles) |
| `openapi` | e.g. `3.0.3` → target `3.1.0` |

`version` MUST be an exact pin (SemVer or dialect pin string). The tokens
`latest`, `*`, empty string, and floating ranges (`^`, `~`, `>=`) are **reject**.

### 3. Feature vocabulary

```json
"feature_vocabulary": {
  "supported": [
    {"id": "myst.directive.admonition", "class": "transformable"},
    {"id": "md.fenced_code", "class": "safe"}
  ],
  "unsupported": [
    {"id": "myst.directive.include", "class": "decision_required"},
    {"id": "openapi.discriminator.mapping", "class": "unsupported"}
  ]
}
```

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | Stable dotted feature id |
| `class` | yes | One of `safe`, `transformable`, `decision_required`, `unsupported`, `malformed` |

Both proposed profiles MUST express their surface using only these classes.
Converters MUST NOT invent parallel enum names.

### 4. Compatibility policy

```json
"compatibility_policy": {
  "policy_id": "openapi-client-server-v1",
  "default_action": "report",
  "rules": [
    {"id": "breaking.path.remove", "severity": "breaking", "action": "block"},
    {"id": "info.description.change", "severity": "informational", "action": "allow"}
  ]
}
```

| Field | Required | Meaning |
| --- | --- | --- |
| `policy_id` | yes | Stable policy name |
| `default_action` | yes | One of `allow`, `report`, `block`, `decision_required` |
| `rules[]` | yes | May be empty; each rule has `id`, `severity`, `action` |
| `severity` | per rule | One of `breaking`, `behavioral`, `informational` |
| `action` | per rule | Same enum as `default_action` |

Docs profiles use the same object; their rules name doc-semantics impacts
(e.g. `nav.link.break`) rather than inventing a second policy schema.

### 5. Tool identities (`transformer` / `validator`)

```json
"transformer": {
  "name": "orrery/docs-myst-to-mdx",
  "version": "1.0.0",
  "digest": "<sha256 of transformer release artifact or image pin>"
},
"validator": {
  "name": "orrery/docs-mdx-validate",
  "version": "1.0.0",
  "digest": "<sha256 …>"
}
```

All three of `name`, `version`, `digest` are required. Receipts copy these
identities so a verifier recovers exact tool pins without calling Orrery.

### 6. Execution locality

| Value | Meaning |
| --- | --- |
| `agent_local` | Transform runs in the caller's environment on caller-held bytes |
| `creator_owned_tooling` | Publisher-owned tool the creator operates; Orrery does not host repos |
| `orrery_coord_only` | Orrery seals policy/artifacts/receipts only; never ingests arbitrary repos |

Default for public migration stars: `agent_local` or `creator_owned_tooling`.
`orrery_coord_only` is for constellation coordination receipts that never saw
raw source.

### 7. Retention / redaction defaults

```json
"retention_redaction": {
  "receipt_includes": ["digests", "safe_metadata", "tool_versions", "findings_summary"],
  "receipt_excludes_by_default": ["source_bytes", "target_bytes", "full_patch_text", "private_paths"],
  "max_finding_message_bytes": 512,
  "max_diagnostics_bytes": 65536
}
```

Receipts retain digests and safe metadata by default, not repository contents.
Leaves MAY attach a separate bounded artifact for the patch; the receipt only
binds its digest.

### 8. Profile digest (canonical bytes)

```text
profile_digest = sha256_hex(canonical_json(profile_without_profile_digest))

canonical_json(obj) =
  UTF-8 JSON with lexicographic key sort at every object level,
  separators "," and ":", ensure_ascii=false, no insignificant whitespace,
  NFC-normalize all string values before serialize
```

Same separator/sort rules as
[envelope-verification.md](../verification/envelope-verification.md).
Verifiers MUST recompute and reject mismatch.

### 9. Floating request → pinned profile resolution

Callers may ask for a **floating request** (family + optional constraints).
Resolution is deterministic and MUST be recorded on the run:

```text
FloatingMigrationRequest:
  family          # e.g. "docs/myst-to-mdx" | "api-spec/openapi-upgrade"
  source_hint?    # optional observed source kind/version
  policy_id?      # optional compatibility_policy.policy_id
  constraints?    # optional { "target_kind"?, "max_profile_major"? }

resolve(request, catalog) → PinnedProfileRef:
  profile_id
  version           # exact SemVer
  profile_digest
  resolution_reason # short enum string
```

Rules:

1. Catalog lookup by `family` yields candidate profiles with matching
   `profile_id` prefix or declared `family` alias in catalog metadata
   (catalog is outside the profile document; aliases are not root side channels).
2. Prefer exact `source_hint` match on `source.kind` + `source.version`.
3. Among matches, choose the highest SemVer `version` whose major is within
   `constraints.max_profile_major` if set; otherwise highest SemVer.
4. If `policy_id` is set, require equality with
   `compatibility_policy.policy_id`.
5. If zero or ambiguous after the above, **fail closed** with
   `resolution_reason = "no_unique_profile"` — never invent a pin.
6. `latest` as a user target string is rejected before catalog lookup.

The run receipt stores `PinnedProfileRef`, never the floating request alone.

### 10. Stage outputs

Modes are explicit: `analyze`, `plan`, `apply`, `validate`. No implicit apply
(saga [#160](https://github.com/lbliii/orrery/issues/160)).

| Stage / mode | Output artifact | Required fields (digest-bound) |
| --- | --- | --- |
| `analyze` | `analysis` | `source_manifest_digest`, `findings[]` (`feature_id`, `class`, `path`, `span?`, `finding_digest`), `analysis_digest` |
| `plan` | `plan` | `analysis_digest`, `profile_digest`, `compatibility_policy.policy_id`, `planned_ops[]`, `plan_digest` |
| `apply` | `change_bundle` | `plan_digest`, `patch_digest`, `file_entries[]` (`path`, `source_digest`, `target_digest`), `mapping_digest`, `warnings[]` (safe), `bundle_digest` |
| `validate` | `validation` | `bundle_digest`, `validator` identity copy, `passed` (bool), `findings[]`, `diagnostics_digest`, `validation_digest` |

`apply` consumes **only** the exact `plan_digest` it was sealed against.
`change_bundle` never implies repository write authority.

### 11. Idempotency / replay key

```text
replay_key = sha256_hex(canonical_json({
  "source_manifest_digest": "...",
  "profile_digest": "...",
  "mode": "analyze|plan|apply|validate",
  "policy_id": "<compatibility_policy.policy_id>"
}))
```

A compatible rerun MAY reuse a sealed stage output for the same `replay_key`.
Any change to source, profile, mode, or policy yields a new key; reuse across
mismatched keys is **reject**.

### 12. Composite migration receipt

Terminal composite receipts for a migration run MUST bind:

| Field | Required | Meaning |
| --- | --- | --- |
| `schema_version` | yes | `"migration-receipt/v1"` |
| `profile_id` | yes | From pinned profile |
| `profile_version` | yes | SemVer |
| `profile_digest` | yes | Exact pin |
| `source` / `target` | yes | Copied pinned `{kind, version}` |
| `transformer` / `validator` | yes | Copied `{name, version, digest}` |
| `execution_locality` | yes | From profile |
| `mode` | yes | Terminal mode sealed |
| `source_manifest_digest` | yes | Content-addressed source inventory |
| `analysis_digest` | if analyze+ | Stage digest or null if mode skipped |
| `plan_digest` | if plan+ | |
| `bundle_digest` | if apply+ | |
| `validation_digest` | if validate+ | |
| `validation_passed` | if validate | bool; MUST be false when validator failed |
| `replay_key` | yes | §11 |
| `retention_redaction` | yes | Policy id or inline echo of defaults applied |
| `cites` | no | DecisionReceipt digests per [ADR 0006](./0006-decision-receipt.md) |
| `receipt_digest` | yes | `sha256` of canonical receipt **excluding** this field and Envelope signature |

Standalone verify procedure:

1. Verify Envelope per
   [envelope-verification.md](../verification/envelope-verification.md).
2. Recompute `profile_digest` against the published profile bytes; require match.
3. Confirm `target.version` / tool `version`+`digest` fields are present and
   not floating tokens.
4. Recompute stage digests the verifier holds (or fetch artifacts by digest)
   and require equality with receipt fields.
5. Reject if `validation_passed === true` while `validation` findings contain
   any `severity: breaking` with action `block`, or while validator `passed`
   is false.

### 13. Representability (acceptance of this freeze)

Both profiles below MUST serialize under §1–§8 with **no** root side channels:

**A. MyST → MDX baseline**

```json
{
  "schema_version": "migration-profile/v1",
  "profile_id": "docs/myst-to-mdx-baseline",
  "version": "1.0.0",
  "source": {"kind": "myst-markdown", "version": "1.3.0"},
  "target": {"kind": "mdx", "version": "3.0.0"},
  "feature_vocabulary": {
    "supported": [
      {"id": "md.heading", "class": "safe"},
      {"id": "myst.directive.admonition", "class": "transformable"}
    ],
    "unsupported": [
      {"id": "myst.directive.include", "class": "decision_required"}
    ]
  },
  "compatibility_policy": {
    "policy_id": "docs-mdx-baseline-v1",
    "default_action": "report",
    "rules": [
      {"id": "nav.link.break", "severity": "breaking", "action": "decision_required"}
    ]
  },
  "execution_locality": "agent_local",
  "transformer": {
    "name": "orrery/docs-myst-to-mdx",
    "version": "1.0.0",
    "digest": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  },
  "validator": {
    "name": "orrery/docs-mdx-validate",
    "version": "1.0.0",
    "digest": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  },
  "retention_redaction": {
    "receipt_includes": ["digests", "safe_metadata", "tool_versions", "findings_summary"],
    "receipt_excludes_by_default": ["source_bytes", "target_bytes", "full_patch_text", "private_paths"],
    "max_finding_message_bytes": 512,
    "max_diagnostics_bytes": 65536
  },
  "profile_digest": "<computed>"
}
```

**B. OpenAPI upgrade**

```json
{
  "schema_version": "migration-profile/v1",
  "profile_id": "api-spec/openapi-3-0-to-3-1-safe",
  "version": "1.0.0",
  "source": {"kind": "openapi", "version": "3.0.3"},
  "target": {"kind": "openapi", "version": "3.1.0"},
  "feature_vocabulary": {
    "supported": [
      {"id": "openapi.json_schema.draft2020", "class": "transformable"}
    ],
    "unsupported": [
      {"id": "openapi.discriminator.mapping", "class": "unsupported"}
    ]
  },
  "compatibility_policy": {
    "policy_id": "openapi-client-server-v1",
    "default_action": "report",
    "rules": [
      {"id": "breaking.path.remove", "severity": "breaking", "action": "block"},
      {"id": "info.description.change", "severity": "informational", "action": "allow"}
    ]
  },
  "execution_locality": "agent_local",
  "transformer": {
    "name": "orrery/openapi-upgrade-safe",
    "version": "1.0.0",
    "digest": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
  },
  "validator": {
    "name": "orrery/openapi-validate",
    "version": "1.0.0",
    "digest": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
  },
  "retention_redaction": {
    "receipt_includes": ["digests", "safe_metadata", "tool_versions", "findings_summary"],
    "receipt_excludes_by_default": ["source_bytes", "target_bytes", "full_patch_text", "private_paths"],
    "max_finding_message_bytes": 512,
    "max_diagnostics_bytes": 65536
  },
  "profile_digest": "<computed>"
}
```

### 14. Non-goals

- Implementing converters or validators in this ADR
- Orrery hosting arbitrary customer repositories
- Floating `latest` targets or unpinned tool digests
- Profile-specific root JSON side channels
- Universal conversion or silent LLM rewrite of unsupported semantics
- Swarm VCS / merge reconciliation (ADR 0004/0005)

## Consequences

- Design [#165](https://github.com/lbliii/orrery/issues/165) closes on this ADR;
  workers MUST NOT re-decide field names, digest rules, or resolution.
- Leaf [#166](https://github.com/lbliii/orrery/issues/166) implements stage
  persistence + change bundles against §10–§11.
- Leaf [#167](https://github.com/lbliii/orrery/issues/167) implements validator
  adapter + composite receipt against §12.
- Leaf [#168](https://github.com/lbliii/orrery/issues/168) stores golden
  profile JSON for §13 examples A/B and stage fixtures.
- Epics [#162](https://github.com/lbliii/orrery/issues/162) /
  [#163](https://github.com/lbliii/orrery/issues/163) publish concrete profiles
  only as documents conforming to this schema.
- Constellations under [#164](https://github.com/lbliii/orrery/issues/164)
  inherit `cites` + lease rules from ADR 0006/0007; migration-specific seal
  fields remain those in §12.
