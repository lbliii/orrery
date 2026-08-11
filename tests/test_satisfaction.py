"""MCP rate tool and satisfaction store (#68)."""

from __future__ import annotations

import logging

import pytest

from dogfood import signed_world_time_receipt, verify_receipt
from trust.satisfaction import (
    InMemorySatisfactionStore,
    get_satisfaction_store,
    submit_rate,
)

STAR_NAME = "orrery/world-time"
CONTENT_DIGEST = "sha256:abc123"


@pytest.fixture
def store() -> InMemorySatisfactionStore:
    return InMemorySatisfactionStore()


@pytest.fixture(autouse=True)
def _isolate_default_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests from leaking ratings into the process-wide stub."""
    fresh = InMemorySatisfactionStore()
    monkeypatch.setattr("trust.satisfaction._default_store", fresh)


@pytest.mark.issue(68)
def test_happy_path_put_with_verified_receipt(store: InMemorySatisfactionStore) -> None:
    receipt, verified = signed_world_time_receipt()
    assert verified is True

    result = submit_rate(
        star_name=STAR_NAME,
        content_digest=CONTENT_DIGEST,
        verdict="useful",
        envelope_id=str(receipt["nonce"]),
        receipt=receipt,
        store=store,
        verify_receipt=verify_receipt,
    )

    assert result["status"] == "ok"
    stored = result["record"]
    assert isinstance(stored, dict)
    assert stored["star_name"] == STAR_NAME
    assert stored["verdict"] == "useful"
    assert stored["envelope_id"] == receipt["nonce"]

    fetched = store.get_for_receipt(
        content_digest=CONTENT_DIGEST,
        envelope_id=str(receipt["nonce"]),
        call_attempt_id=None,
    )
    assert fetched is not None
    assert fetched.verdict == "useful"


@pytest.mark.issue(68)
def test_reject_without_receipt_authority(store: InMemorySatisfactionStore) -> None:
    missing = submit_rate(
        star_name=STAR_NAME,
        content_digest=CONTENT_DIGEST,
        verdict="useful",
        store=store,
        verify_receipt=verify_receipt,
    )
    assert missing["status"] == "rejected"
    assert missing["error"] == "missing_receipt_authority"

    receipt, _ = signed_world_time_receipt()
    no_receipt = submit_rate(
        star_name=STAR_NAME,
        content_digest=CONTENT_DIGEST,
        verdict="useful",
        envelope_id=str(receipt["nonce"]),
        store=store,
        verify_receipt=verify_receipt,
    )
    assert no_receipt["status"] == "rejected"
    assert no_receipt["error"] == "missing_receipt"


@pytest.mark.issue(68)
def test_digest_keyed_get(store: InMemorySatisfactionStore) -> None:
    digest_a = "sha256:aaa"
    digest_b = "sha256:bbb"

    submit_rate(
        star_name=STAR_NAME,
        content_digest=digest_a,
        verdict="stale",
        call_attempt_id="attempt-1",
        store=store,
        verify_receipt=verify_receipt,
    )
    submit_rate(
        star_name=STAR_NAME,
        content_digest=digest_b,
        verdict="broken",
        call_attempt_id="attempt-2",
        store=store,
        verify_receipt=verify_receipt,
    )

    assert store.get_for_receipt(
        content_digest=digest_a,
        envelope_id=None,
        call_attempt_id="attempt-1",
    ) is not None
    assert store.get_for_receipt(
        content_digest=digest_b,
        envelope_id=None,
        call_attempt_id="attempt-2",
    ) is not None
    assert store.get_for_receipt(
        content_digest=digest_a,
        envelope_id=None,
        call_attempt_id="attempt-2",
    ) is None

    agg = store.aggregate(star_name=STAR_NAME, content_digest=digest_a)
    assert agg.total == 1
    assert agg.counts == {"stale": 1}


@pytest.mark.issue(68)
def test_no_wallet_side_effects(store: InMemorySatisfactionStore, caplog) -> None:
    receipt, verified = signed_world_time_receipt()
    assert verified is True

    with caplog.at_level(logging.WARNING):
        result = submit_rate(
            star_name=STAR_NAME,
            content_digest=CONTENT_DIGEST,
            verdict="useful",
            envelope_id=str(receipt["nonce"]),
            receipt=receipt,
            store=store,
            verify_receipt=verify_receipt,
        )

    assert result["status"] == "ok"
    assert "commerce.charge_stub" not in caplog.text
    assert "commerce.refund_stub" not in caplog.text


@pytest.mark.issue(68)
def test_failed_call_token_path(store: InMemorySatisfactionStore) -> None:
    result = submit_rate(
        star_name=STAR_NAME,
        content_digest="sha256:deadbeef",
        verdict="broken",
        call_attempt_id="fail-attempt-99",
        store=store,
        verify_receipt=verify_receipt,
    )
    assert result["status"] == "ok"
    assert result["record"]["call_attempt_id"] == "fail-attempt-99"
    assert "envelope_id" not in result["record"]


@pytest.mark.issue(68)
def test_reject_invalid_receipt(store: InMemorySatisfactionStore) -> None:
    receipt, _ = signed_world_time_receipt()
    forged = dict(receipt)
    forged["nonce"] = "tampered"

    result = submit_rate(
        star_name=STAR_NAME,
        content_digest="sha256:deadbeef",
        verdict="useful",
        envelope_id=str(receipt["nonce"]),
        receipt=forged,
        store=store,
        verify_receipt=verify_receipt,
    )
    assert result["status"] == "rejected"
    assert result["error"] == "invalid_receipt"


@pytest.mark.issue(68)
def test_default_store_singleton() -> None:
    store = get_satisfaction_store()
    assert isinstance(store, InMemorySatisfactionStore)
