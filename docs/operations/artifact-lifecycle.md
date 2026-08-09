# Artifact lifecycle and delivery

This document describes the artifact behavior deployed by the current managed
execution work. It is deliberately narrower than the intended product design.

## Current retention and access behavior

Produced artifacts are assigned a 15-minute expiry at publication. While an
artifact is `available` and before that expiry, the application can retrieve
its object by opaque artifact ID. After expiry, the application treats it as
unavailable and returns `404` from the artifact route.

This is an **access TTL**, not physical retention. No scheduled reaper and no
bucket lifecycle deletion rule are currently deployed. Artifact bytes can
therefore remain in object storage after the 15-minute access window, and the
metadata record can also remain in Postgres. Do not promise deletion, data
minimization, or a retention deadline beyond access expiry.

## States and publication failures

Artifact metadata uses the following state machine:

| State | Meaning now |
| --- | --- |
| `pending_upload` | Metadata intent was persisted before the object upload. |
| `available` | Upload completed and the metadata was marked available. |
| `deleting` | Reserved for a future deletion worker after it claims a pending or available artifact. |
| `deleted` | Reserved for a future deletion worker after object deletion. |

On synchronous publication failure after intent creation, the publisher calls
object-storage delete and does not mark the record `available`. This is best
effort cleanup, not a durable deletion workflow: a process or storage failure
can still leave a `pending_upload` record or object behind. The `deleting` and
`deleted` transitions exist in the repository contract but are not presently
driven by a scheduled worker.

## Live download API limits

`GET /artifacts/{artifact_id}` is an opaque-ID download route. It has no list,
search, filename, or digest lookup endpoint, and an unknown, unavailable, or
expired ID returns `404`. The opaque ID is the practical bearer capability in
the current route; callers should not put it in public logs or URLs that they
do not intend to share.

The live route is currently PDF-oriented: it emits `application/pdf` and a
`.pdf` attachment name. The managed CSV and image workloads can persist their
correct object metadata and bytes, but they do **not** yet have a content-type
correct public delivery endpoint. They are demonstrable through their managed
run receipt and storage adapter tests, not a complete public CSV/image download
surface.

## Verification and attestation boundary

The managed run's terminal receipt records the opaque artifact ID, content
metadata, and `sha256:<digest>`. The `result` MCP tool returns that terminal
receipt inside Chirp's signed envelope. An agent should verify the envelope
with the Star's published key, fetch the artifact during its access window,
then calculate SHA-256 over the received bytes and compare it to the signed
receipt.

That proves what Orrery's worker published and what the agent received from
the delivery path at verification time. It does **not** prove that an agent
saved, retained, displayed, or later used a particular local copy. Orrery has
no observation channel for an agent's local filesystem or downstream tools,
and must not attest that local-copy claim without a new archive/acknowledgement
protocol.

## Planned: cleanup and local-copy acknowledgement

The following is a proposal, not deployed behavior.

1. Run a durable expiry reaper that selects expired `pending_upload` and
   `available` records, transitions them atomically to `deleting`, deletes the
   exact object key, then records `deleted`. It must retry idempotently,
   report orphan cleanup metrics, and be paired with a bucket lifecycle rule
   as a second safety net.
2. Add an artifact delivery endpoint that authorizes a receipt holder and
   emits the stored content type, filename, and integrity headers for every
   supported output type.
3. Define a signed `archive_ack` protocol: an agent signs a statement binding
   its agent identity, run ID, artifact ID, receipt digest, local digest,
   timestamp, and retention claim. Orrery verifies and stores that statement
   as an **agent assertion**, never as independent proof of the agent's local
   storage. Revocation and acknowledgement expiry must be explicit.
