from datetime import UTC, datetime, timedelta

import pytest

from creator_callbacks import (
    CallbackDisposition,
    CallbackReplayError,
    CreatorCallback,
    CreatorCallbackService,
    CreatorJobRequest,
    CreatorProtocolError,
    ProtocolSigner,
    ProviderHealth,
    ProviderProvenance,
    UploadCapability,
)
from runs import InMemoryRunRepository, RunRecord, RunState


def _now() -> datetime:
    return datetime(2026, 8, 9, tzinfo=UTC)


def _signer() -> ProtocolSigner:
    return ProtocolSigner(b"a creator callback shared secret")


def _request(*, deadline: datetime | None = None) -> CreatorJobRequest:
    deadline = deadline or _now() + timedelta(minutes=10)
    return CreatorJobRequest(
        run_id="run-1",
        input_sha256="a" * 64,
        deadline=deadline,
        upload=UploadCapability(
            artifact_id="artifact-1",
            url="https://objects.example/upload/one",
            method="PUT",
            expires_at=deadline - timedelta(seconds=1),
            required_headers={"Content-Type": "application/pdf"},
        ),
        callback_url="https://orrery.lol/internal/creator-callback",
    )


def _callback(*, delivery_id: str = "delivery-1", outcome: str = "succeeded") -> CreatorCallback:
    return CreatorCallback(
        delivery_id=delivery_id,
        run_id="run-1",
        outcome=outcome,
        completed_at=_now(),
        provenance=ProviderProvenance("creator.example", "job-88", "2026.8", "us-east-1"),
        health=ProviderHealth("healthy", _now(), latency_ms=42),
        artifact_id="artifact-1" if outcome == "succeeded" else None,
        failure_code="render_failed" if outcome == "failed" else None,
        failure_detail="bad markup" if outcome == "failed" else None,
    )


def _repository(state: RunState) -> InMemoryRunRepository:
    repository = InMemoryRunRepository(clock=_now)
    record = repository.create_or_get(
        RunRecord(
            run_id="run-1",
            caller_id="caller",
            idempotency_key="idempotency",
            budget={},
            executor="creator",
        )
    )
    for next_state in (RunState.QUEUED, RunState.RUNNING, state):
        if record.state is next_state:
            continue
        record = repository.transition("run-1", from_state=record.state, to_state=next_state)  # type: ignore[assignment]
    return repository


def test_signed_job_binds_digest_deadline_and_constrained_upload_capability() -> None:
    signer = _signer()
    signed = signer.sign_job(_request())

    assert signer.verify_job(signed, now=_now()).upload.method == "PUT"

    tampered = CreatorJobRequest(**{**signed.request.__dict__, "input_sha256": "b" * 64})
    with pytest.raises(CreatorProtocolError, match="signature"):
        signer.verify_job(type(signed)(request=tampered, signature=signed.signature), now=_now())


def test_expired_job_or_upload_capability_is_rejected() -> None:
    signer = _signer()
    signed = signer.sign_job(_request(deadline=_now() + timedelta(seconds=1)))
    with pytest.raises(CreatorProtocolError, match="expired"):
        signer.verify_job(signed, now=_now() + timedelta(seconds=2))

    request = _request()
    invalid = CreatorJobRequest(
        **{
            **request.__dict__,
            "upload": UploadCapability(
                **{**request.upload.__dict__, "expires_at": request.deadline + timedelta(seconds=1)}
            ),
        }
    )
    with pytest.raises(CreatorProtocolError, match="outlive"):
        signer.sign_job(invalid)


def test_callback_finalizes_success_with_auditable_provider_receipt() -> None:
    repository = _repository(RunState.UPLOADING)
    signer = _signer()
    service = CreatorCallbackService(repository, signer)
    callback = _callback()

    assert (
        service.receive(callback, signature=signer.sign_callback(callback))
        is CallbackDisposition.FINALIZED
    )
    record = repository.get("run-1")
    assert record is not None and record.state is RunState.SUCCEEDED
    assert record.terminal_receipt == {
        "kind": "creator_callback",
        "artifact_id": "artifact-1",
        "failure": None,
        "provenance": {
            "provider_id": "creator.example",
            "provider_job_id": "job-88",
            "executor_version": "2026.8",
            "region": "us-east-1",
        },
        "provider_health": {
            "status": "healthy",
            "observed_at": "2026-08-09T00:00:00Z",
            "latency_ms": 42,
            "detail": None,
        },
        "completed_at": "2026-08-09T00:00:00Z",
    }


def test_delivery_retry_is_not_a_second_completion_attempt() -> None:
    repository = _repository(RunState.UPLOADING)
    signer = _signer()
    service = CreatorCallbackService(repository, signer)
    callback = _callback()
    signature = signer.sign_callback(callback)

    assert service.receive(callback, signature=signature) is CallbackDisposition.FINALIZED
    assert service.receive(callback, signature=signature) is CallbackDisposition.DELIVERY_RETRY


def test_distinct_delivery_of_same_terminal_completion_is_idempotent() -> None:
    repository = _repository(RunState.UPLOADING)
    signer = _signer()
    service = CreatorCallbackService(repository, signer)
    first, second = _callback(delivery_id="delivery-1"), _callback(delivery_id="delivery-2")

    assert (
        service.receive(first, signature=signer.sign_callback(first))
        is CallbackDisposition.FINALIZED
    )
    assert (
        service.receive(second, signature=signer.sign_callback(second))
        is CallbackDisposition.COMPLETION_IDEMPOTENT
    )


def test_reused_delivery_id_with_changed_callback_is_rejected() -> None:
    repository = _repository(RunState.UPLOADING)
    signer = _signer()
    service = CreatorCallbackService(repository, signer)
    first, changed = _callback(), _callback(outcome="failed")
    service.receive(first, signature=signer.sign_callback(first))

    with pytest.raises(CallbackReplayError, match="reused"):
        service.receive(changed, signature=signer.sign_callback(changed))


def test_failure_finalizes_from_running_and_invalid_callback_auth_does_not_mutate() -> None:
    repository = _repository(RunState.RUNNING)
    signer = _signer()
    service = CreatorCallbackService(repository, signer)
    callback = _callback(outcome="failed")

    with pytest.raises(CreatorProtocolError, match="signature"):
        service.receive(callback, signature="not-a-signature")
    assert repository.get("run-1").state is RunState.RUNNING  # type: ignore[union-attr]

    assert (
        service.receive(callback, signature=signer.sign_callback(callback))
        is CallbackDisposition.FINALIZED
    )
    assert repository.get("run-1").terminal_reason == "creator_failed:render_failed"  # type: ignore[union-attr]
