# Artifact lifecycle and delivery

This document describes the artifact behavior deployed by the current managed
execution work. It is deliberately narrower than the intended product design.

## Current retention and access behavior

Produced artifacts are assigned a 15-minute expiry at publication. While an
artifact is `available` and before that expiry, the application can retrieve
its object by opaque artifact ID. After expiry, the application treats it as
unavailable and returns `404` from the artifact route.

Physical retention is enforced by the managed worker's bounded cleanup tick.
It atomically claims expired `pending_upload` or `available` records, moves
them to `deleting`, deletes the exact object key, and leaves a `deleted`
metadata tombstone. Storage failures remain `deleting` (never downloadable)
and retry after a safe window. The worker starts a pass immediately, then runs
every five minutes by default, with a maximum batch of 100 records. Railway
Buckets do not currently support native lifecycle configuration, so this
durable reaper is the enforcement mechanism in production. Do not promise a
tighter deletion deadline than worker interval, batch capacity, and storage
retry behavior.

## States and publication failures

Artifact metadata uses the following state machine:

| State | Meaning now |
| --- | --- |
| `pending_upload` | Metadata intent was persisted before the object upload. |
| `available` | Upload completed and the metadata was marked available. |
| `deleting` | Claimed by cleanup; unavailable and safely retried after storage failure. |
| `deleted` | Object deletion completed; retained as a metadata tombstone. |

On synchronous publication failure after intent creation, the publisher calls
object-storage delete and does not mark the record `available`. This is best
effort cleanup. Any resulting expired `pending_upload` object is covered by
the same durable cleanup worker.

## Live download API limits

`GET /artifacts/{artifact_id}` is an opaque-ID download route. It has no list,
search, filename, or digest lookup endpoint, and an unknown, unavailable, or
expired ID returns `404`. The opaque ID is the practical bearer capability in
the current route; callers should not put it in public logs or URLs that they
do not intend to share.

The route serves the stored content type and a sanitized stored attachment
filename for supported PDF, CSV, and PNG artifacts. It proxies bytes rather
than exposing a storage capability URL, adds `Cache-Control: no-store` and
`X-Content-Type-Options: nosniff`, and emits a download audit event containing
only artifact ID, outcome, and content type. The public route treats the opaque
ID as the current receipt-holder capability; `private` policy artifacts have no
public owner-authentication route and fail closed.

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

## Remaining delivery work and local-copy acknowledgement

The following is a proposal, not deployed behavior.

1. Add an artifact delivery endpoint that authorizes a receipt holder and
   emits the stored content type, filename, and integrity headers for every
   supported output type.
2. Define a signed `archive_ack` protocol: an agent signs a statement binding
   its agent identity, run ID, artifact ID, receipt digest, local digest,
   timestamp, and retention claim. Orrery verifies and stores that statement
   as an **agent assertion**, never as independent proof of the agent's local
   storage. Revocation and acknowledgement expiry must be explicit.
