# Verified Release Evidence Pack backlog

## Outcome

An agent or CI job submits a release identifier, commit metadata, and a small list of official sources. Orrery returns:

- a real, downloadable PDF evidence pack;
- a machine-readable composite receipt; and
- a signature that an independent verifier can validate.

The release can be `pass`, `fail`, or `inconclusive`. A failed or unverifiable child result must never produce `pass`.

## Scope guardrails

This is the first sellable vertical slice. Do not add more generic public stars, a marketplace, billing, or private-namespace administration until this flow is demonstrably useful end to end.

## Demonstration script

1. Start a CI run with a release ID, commit SHA, policy, and two official source URLs.
2. `source-watch` retrieves each source and seals its URL, timestamp, excerpt, and normalized digest.
3. `release-evidence` evaluates the defined policy and produces `release-evidence.pdf` plus `receipt.json`.
4. Download the PDF, inspect its pass/fail verdict and evidence table, then run `orrery verify receipt.json`.
5. Alter a signed field or the PDF bytes; verification fails with a specific reason.

## P0: make the outcome real

### ORR-001 — Deliver a real PDF artifact

**Priority:** P0
**Owner:** Platform / rendering
**Depends on:** artifact storage and a sandboxed PDF renderer

Replace the receipt-only `html-to-pdf` stub with a renderer that persists a valid PDF and provides a time-limited download URL.

**Acceptance criteria**

- Given HTML input, the response includes `artifact_url`, `sha256`, `content_type: application/pdf`, `byte_length`, and `page_count`.
- The URL downloads a PDF that opens in standard viewers and whose SHA-256 matches the response.
- Expired URLs return a clear expiration error.
- Rendering runs without access to arbitrary external network resources; external assets are disabled or allowlisted initially.

### ORR-002 — Canonical, machine-readable Envelope v1

**Priority:** P0
**Owner:** Protocol
**Depends on:** a decision on canonical signing serialization

Replace prose-wrapped `Envelope(...)` strings with one published JSON schema used by every star.

**Acceptance criteria**

- Every result validates against the published schema and includes `schema_version`, `star`, `issued_at`, `input_digest`, `claims`, `artifacts`, `evidence`, `signature`, and `key_id`.
- Error responses use a documented structured format.
- Contract tests cover the live request and response examples for every public star.
- Any compatibility bridge is explicit and versioned; the default is structured output.

### ORR-003 — Independent verification: keys, API, and CLI

**Priority:** P0
**Owner:** Trust / developer experience
**Depends on:** ORR-002 and signing-key management

Make “verified” an action a customer can perform, not a label displayed by Orrery.

**Acceptance criteria**

- Publish key discovery by `key_id`, including validity windows and rotation guidance.
- `orrery verify receipt.json` validates the schema, signature, linked artifact digests, and receipt freshness.
- Tampering with a signed field or PDF byte fails non-zero and says why.
- A new user can complete the verification demo in five commands or fewer.

### ORR-004 — Repair `source-watch` and solidify evidence

**Priority:** P0
**Owner:** Evidence star
**Depends on:** ORR-002

Make source evidence safe to use as release evidence.

**Acceptance criteria**

- `max_chars` accepts the type promised by the schema (prefer an integer); documentation and live behavior match.
- Each result includes canonical URL, retrieval timestamp, normalized digest, retrieval status, and a bounded excerpt or summary.
- An upstream timeout, block, or rate limit produces `inconclusive` or `unavailable`, never an implied success.
- Tests execute every documented input/output example.

### ORR-005 — Ship the `release-evidence` composite workflow

**Priority:** P0
**Owner:** Workflow / policy
**Depends on:** ORR-001 through ORR-004

Create one call that combines evidence retrieval, PDF creation, and a signed release verdict.

**Acceptance criteria**

- Input accepts release ID, commit SHA, a small policy configuration, and a source list.
- Output includes a deterministic `pass`, `fail`, or `inconclusive` verdict; the downloadable PDF; and a composite receipt referencing every child receipt and artifact digest.
- Any failed or unverifiable source/artifact prevents `pass`.
- The initial policy is intentionally small and documented, with deterministic rules rather than free-form judgement.

## P1: make it easy to adopt and hard to doubt

### ORR-006 — Evidence Pack report template

**Priority:** P1
**Depends on:** ORR-001, ORR-004, ORR-005

Render a report a release manager can read in under two minutes.

**Acceptance criteria**

- The PDF shows release metadata, final verdict, source table, policy results, digests, signing identity, and a copyable verification command or QR/link.
- Pass and fail variants are readable in standard PDF viewers.
- The PDF is rendered from the same canonical receipt payload it summarizes, preventing drift.

### ORR-007 — GitHub Actions reference integration

**Priority:** P1
**Depends on:** ORR-005 and the chosen authentication design

Demonstrate the workflow where teams already release software.

**Acceptance criteria**

- A sample action runs on a tag or manual dispatch and submits commit metadata plus configured sources.
- It uploads `release-evidence.pdf` and `receipt.json` as workflow artifacts.
- The job fails on `fail` or `inconclusive`.
- Setup is copy-pasteable; credentials are short-lived/scoped and redact from logs.

### ORR-008 — Trust regression suite and catalog consistency

**Priority:** P1
**Depends on:** ORR-001 through ORR-005

Prevent attractive demo pages from drifting away from the trusted system.

**Acceptance criteria**

- Gaze, Resolve, Star pages, and the console show the same canonical version and content digest.
- Automated probes cover success, invalid input, schema validation, checksum verification, expired URLs, and signature tampering.
- Reliability distinguishes upstream dependency outages from product regressions and includes controlled fixtures in CI.

### ORR-009 — One working private namespace pilot

**Priority:** P1
**Depends on:** ORR-005, ORR-008

Turn the namespace claim into a usable pilot path for one team.

**Acceptance criteria**

- The tenant MCP endpoint resolves from an external client and requires authorized access.
- The team can create, run, and retain release-evidence receipts in its namespace.
- The UI uses a working onboarding path, not a placeholder CTA.
- Audit retention and access boundaries are documented for the pilot.

## Sequencing

`ORR-001` and `ORR-002` can begin together. Then complete `ORR-003` and `ORR-004`, followed by `ORR-005`. At that point the demo is real. `ORR-006`–`ORR-009` make it usable, believable, and adoptable.

## Definition of demonstrable value

The slice is ready to show when a third party can run one CI command, receive a usable PDF and JSON receipt, independently prove that neither was altered, and see the run fail when required evidence is missing or stale.
