"""A small, transport-neutral protocol for creator-owned asynchronous jobs.

Orrery signs a narrowly scoped job description and creators sign their terminal
callback.  HTTP/MCP adapters can carry these JSON-compatible objects without
embedding their routing or credential policy in this module.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol

from runs import RunConflictError, RunState


class CreatorProtocolError(ValueError):
    """A request or callback is malformed, unauthorized, or expired."""


class CallbackReplayError(CreatorProtocolError):
    """A delivery ID was reused with different signed callback content."""


@dataclass(frozen=True)
class UploadCapability:
    """The exact artifact upload authority granted to one creator job."""

    artifact_id: str
    url: str
    method: str
    expires_at: datetime
    required_headers: Mapping[str, str]


@dataclass(frozen=True)
class CreatorJobRequest:
    """Signed input to a creator-owned job; never includes general credentials."""

    run_id: str
    input_sha256: str
    deadline: datetime
    upload: UploadCapability
    callback_url: str


@dataclass(frozen=True)
class SignedCreatorJobRequest:
    request: CreatorJobRequest
    signature: str


@dataclass(frozen=True)
class ProviderHealth:
    status: str
    observed_at: datetime
    latency_ms: int | None = None
    detail: str | None = None


@dataclass(frozen=True)
class ProviderProvenance:
    provider_id: str
    provider_job_id: str
    executor_version: str | None = None
    region: str | None = None


@dataclass(frozen=True)
class CreatorCallback:
    """One terminal provider event, identified separately from its delivery."""

    delivery_id: str
    run_id: str
    outcome: str
    completed_at: datetime
    provenance: ProviderProvenance
    health: ProviderHealth
    artifact_id: str | None = None
    failure_code: str | None = None
    failure_detail: str | None = None


class CallbackDisposition(StrEnum):
    FINALIZED = "finalized"
    COMPLETION_IDEMPOTENT = "completion_idempotent"
    DELIVERY_RETRY = "delivery_retry"


class FinalizableRunRepository(Protocol):
    def finalize(
        self,
        run_id: str,
        *,
        from_state: RunState,
        state: RunState,
        reason: str,
        receipt: Mapping[str, Any],
    ) -> Any: ...


class ProtocolSigner:
    """HMAC signer with deterministic JSON canonicalization for a shared secret."""

    def __init__(self, secret: bytes) -> None:
        if len(secret) < 16:
            raise ValueError("creator callback secret must be at least 16 bytes")
        self._secret = secret

    def sign_job(self, request: CreatorJobRequest) -> SignedCreatorJobRequest:
        _validate_job_request(request)
        return SignedCreatorJobRequest(
            request=request, signature=self.sign_payload(_job_payload(request))
        )

    def verify_job(
        self, signed: SignedCreatorJobRequest, *, now: datetime | None = None
    ) -> CreatorJobRequest:
        _validate_job_request(signed.request)
        self.verify_payload(_job_payload(signed.request), signed.signature)
        if signed.request.deadline <= (now or datetime.now(UTC)):
            raise CreatorProtocolError("creator job request has expired")
        return signed.request

    def sign_callback(self, callback: CreatorCallback) -> str:
        _validate_callback(callback)
        return self.sign_payload(_callback_payload(callback))

    def verify_callback(self, callback: CreatorCallback, signature: str) -> None:
        _validate_callback(callback)
        self.verify_payload(_callback_payload(callback), signature)

    def sign_payload(self, payload: Mapping[str, Any]) -> str:
        return hmac.new(self._secret, _canonical_json(payload), hashlib.sha256).hexdigest()

    def verify_payload(self, payload: Mapping[str, Any], signature: str) -> None:
        expected = self.sign_payload(payload)
        if not hmac.compare_digest(expected, signature):
            raise CreatorProtocolError("creator protocol signature is invalid")


class CallbackReplayGuard:
    """Tracks delivery IDs; identical redelivery is safe, altered replay is not."""

    def __init__(self) -> None:
        self._deliveries: dict[tuple[str, str], str] = {}

    def record(self, callback: CreatorCallback) -> bool:
        key = (callback.provenance.provider_id, callback.delivery_id)
        digest = hashlib.sha256(_canonical_json(_callback_payload(callback))).hexdigest()
        previous = self._deliveries.get(key)
        if previous is None:
            self._deliveries[key] = digest
            return True
        if not hmac.compare_digest(previous, digest):
            raise CallbackReplayError("callback delivery ID was reused with different content")
        return False


class CreatorCallbackService:
    """Authenticates creator terminal callbacks and seals exactly one run result."""

    def __init__(
        self,
        repository: FinalizableRunRepository,
        signer: ProtocolSigner,
        replay_guard: CallbackReplayGuard | None = None,
    ) -> None:
        self._repository = repository
        self._signer = signer
        self._replay_guard = replay_guard or CallbackReplayGuard()

    def receive(self, callback: CreatorCallback, *, signature: str) -> CallbackDisposition:
        self._signer.verify_callback(callback, signature)
        if not self._replay_guard.record(callback):
            return CallbackDisposition.DELIVERY_RETRY
        state, reason = _terminal_result(callback)
        receipt = _receipt(callback)
        # Repositories that expose reads let us distinguish a new terminal
        # completion from a distinct delivery of an already-sealed one.  The
        # guarded finalize remains the authority for the race between read and
        # write, so adapters without reads retain correct finalization safety.
        existing = getattr(self._repository, "get", lambda _run_id: None)(callback.run_id)
        if getattr(existing, "is_terminal", False):
            if (
                existing.state is state
                and existing.terminal_reason == reason
                and existing.terminal_receipt == receipt
            ):
                return CallbackDisposition.COMPLETION_IDEMPOTENT
            raise CreatorProtocolError("run already has a different terminal creator result")
        try:
            result = self._repository.finalize(
                callback.run_id,
                from_state=_callback_source_state(callback),
                state=state,
                reason=reason,
                receipt=receipt,
            )
        except RunConflictError:
            # A distinct provider delivery may repeat an already sealed outcome.
            return CallbackDisposition.COMPLETION_IDEMPOTENT
        if result is None:
            raise CreatorProtocolError("run is not awaiting this creator terminal callback")
        return CallbackDisposition.FINALIZED


def _terminal_result(callback: CreatorCallback) -> tuple[RunState, str]:
    if callback.outcome == "succeeded":
        if callback.artifact_id is None:
            raise CreatorProtocolError("successful callback requires an artifact ID")
        return RunState.SUCCEEDED, "creator_succeeded"
    if callback.outcome == "failed":
        if not callback.failure_code:
            raise CreatorProtocolError("failed callback requires a failure code")
        return RunState.FAILED, f"creator_failed:{callback.failure_code}"
    raise CreatorProtocolError("callback outcome must be succeeded or failed")


def _callback_source_state(callback: CreatorCallback) -> RunState:
    return RunState.UPLOADING if callback.outcome == "succeeded" else RunState.RUNNING


def _receipt(callback: CreatorCallback) -> dict[str, Any]:
    return {
        "kind": "creator_callback",
        "artifact_id": callback.artifact_id,
        "failure": {"code": callback.failure_code, "detail": callback.failure_detail}
        if callback.outcome == "failed"
        else None,
        "provenance": _wire(callback.provenance),
        "provider_health": _wire(callback.health),
        "completed_at": _iso(callback.completed_at),
    }


def _validate_job_request(request: CreatorJobRequest) -> None:
    if not request.run_id or not _is_sha256(request.input_sha256):
        raise CreatorProtocolError("job request requires a run ID and SHA-256 input digest")
    if request.upload.method != "PUT" or not request.upload.artifact_id or not request.upload.url:
        raise CreatorProtocolError("job request requires a constrained PUT upload capability")
    if request.upload.expires_at > request.deadline:
        raise CreatorProtocolError("upload capability must not outlive job deadline")
    if not request.callback_url.startswith("https://"):
        raise CreatorProtocolError("callback URL must use HTTPS")


def _validate_callback(callback: CreatorCallback) -> None:
    if not callback.delivery_id or not callback.run_id:
        raise CreatorProtocolError("callback requires delivery and run IDs")
    if not callback.provenance.provider_id or not callback.provenance.provider_job_id:
        raise CreatorProtocolError("callback requires provider provenance")
    if callback.health.status not in {"healthy", "degraded", "unhealthy", "unknown"}:
        raise CreatorProtocolError("callback health status is invalid")
    if callback.health.latency_ms is not None and callback.health.latency_ms < 0:
        raise CreatorProtocolError("callback health latency cannot be negative")


def _job_payload(request: CreatorJobRequest) -> dict[str, Any]:
    return _wire(request)


def _callback_payload(callback: CreatorCallback) -> dict[str, Any]:
    return _wire(callback)


def _wire(value: Any) -> Any:
    if isinstance(value, datetime):
        return _iso(value)
    if hasattr(value, "__dataclass_fields__"):
        return {key: _wire(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): _wire(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_wire(item) for item in value]
    return value


def _canonical_json(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise CreatorProtocolError("timestamps must be timezone-aware")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value.lower())
