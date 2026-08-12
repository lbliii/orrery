"""Wire envelope verify to prepaid ledger (ADR 0002, #370)."""

from __future__ import annotations

import json
import logging

import pytest
from chirp.testing import TestClient

from commerce import get_ledger, reset_ledger
from commerce.ledger import HoldStatus, LedgerOp
from commerce.stubs import charge_on_verify as stub_charge
from commerce.stubs import refund_on_forge as stub_refund
from commerce.verify_wire import parse_price_per_call_cents

OWNER = "user-verify-1"
PAYMENT_ID = "pay-verify-wire"
PRICE = "$0.02"
PRICE_CENTS = 2


@pytest.fixture
def wallet_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORRERY_WALLET_ENABLED", "1")
    reset_ledger()


def _seed_open_hold(*, payment_id: str = PAYMENT_ID, balance_cents: int = 100) -> None:
    ledger = get_ledger()
    ledger.credit(OWNER, balance_cents, idempotency_key=f"credit-{payment_id}")
    ledger.hold(
        OWNER,
        PRICE_CENTS,
        idempotency_key=payment_id,
        payment_id=payment_id,
        skill="html-to-pdf",
        price_per_call_cents=PRICE_CENTS,
    )


@pytest.mark.issue(370)
def test_parse_price_per_call_cents() -> None:
    assert parse_price_per_call_cents(None) is None
    assert parse_price_per_call_cents("Free") is None
    assert parse_price_per_call_cents("$0.02") == 2
    assert parse_price_per_call_cents("USD 0.25") == 25


@pytest.mark.issue(370)
def test_wallet_disabled_uses_loud_stubs(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="orrery.commerce"):
        charged = stub_charge(
            payment_id=PAYMENT_ID,
            price_per_call=PRICE,
            skill="html-to-pdf",
            nonce="n1",
        )
        refunded = stub_refund(
            payment_id=PAYMENT_ID,
            price_per_call=PRICE,
            skill="html-to-pdf",
            nonce="n1",
        )
    assert charged["stub"] is True
    assert refunded["stub"] is True
    assert "commerce.charge_stub" in caplog.text
    assert "commerce.refund_stub" in caplog.text


@pytest.mark.issue(370)
async def test_verify_ok_captures_hold(
    wallet_enabled: None, example_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dogfood import signed_convert_receipt

    _seed_open_hold()
    receipt, _ = signed_convert_receipt()
    receipt["payment_id"] = PAYMENT_ID
    receipt["price_per_call"] = PRICE
    receipt["owner_id"] = OWNER

    async with TestClient(example_app) as client:
        response = await client.post("/api/envelope/verify", json=receipt)

    assert response.status == 200
    body = json.loads(response.text)
    assert body["verified"] is True
    assert body["commerce"]["status"] == "captured"
    assert body["commerce"]["stub"] is False
    assert body["commerce"]["ledger_op"] == LedgerOp.CAPTURE

    ledger = get_ledger()
    account = ledger.get_account(OWNER)
    assert account.balance_cents == 98
    assert account.held_cents == 0
    hold = ledger.find_hold(PAYMENT_ID)
    assert hold is not None
    assert hold.status == HoldStatus.CAPTURED


@pytest.mark.issue(370)
async def test_forge_fail_releases_hold(
    wallet_enabled: None, example_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dogfood import signed_convert_receipt

    _seed_open_hold()
    receipt, _ = signed_convert_receipt()
    receipt["payment_id"] = PAYMENT_ID
    receipt["price_per_call"] = PRICE
    receipt["owner_id"] = OWNER

    forged = dict(receipt)
    forged["nonce"] = "tampered-nonce"

    async with TestClient(example_app) as client:
        response = await client.post("/api/envelope/verify", json=forged)

    assert response.status == 200
    body = json.loads(response.text)
    assert body["verified"] is False
    assert body["commerce"]["status"] == "released"
    assert body["commerce"]["stub"] is False
    assert body["commerce"]["ledger_op"] == LedgerOp.RELEASE

    ledger = get_ledger()
    account = ledger.get_account(OWNER)
    assert account.balance_cents == 100
    assert account.held_cents == 0
    hold = ledger.find_hold(PAYMENT_ID)
    assert hold is not None
    assert hold.status == HoldStatus.RELEASED


@pytest.mark.issue(370)
async def test_verify_replay_does_not_double_capture(
    wallet_enabled: None, example_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dogfood import signed_convert_receipt

    _seed_open_hold()
    receipt, _ = signed_convert_receipt()
    receipt["payment_id"] = PAYMENT_ID
    receipt["price_per_call"] = PRICE
    receipt["owner_id"] = OWNER

    async with TestClient(example_app) as client:
        first = await client.post("/api/envelope/verify", json=receipt)
        second = await client.post("/api/envelope/verify", json=receipt)

    first_body = json.loads(first.text)
    second_body = json.loads(second.text)
    assert first_body["commerce"]["entry_id"] == second_body["commerce"]["entry_id"]

    ledger = get_ledger()
    capture_entries = [
        entry for entry in ledger.ledger_entries(OWNER) if entry.op == LedgerOp.CAPTURE
    ]
    assert len(capture_entries) == 1
    assert ledger.get_account(OWNER).balance_cents == 98


@pytest.mark.issue(370)
async def test_free_and_null_price_skip_ledger(
    wallet_enabled: None, example_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dogfood import signed_convert_receipt

    receipt, _ = signed_convert_receipt()
    receipt["payment_id"] = PAYMENT_ID
    receipt["price_per_call"] = None

    async with TestClient(example_app) as client:
        ok = await client.post("/api/envelope/verify", json=receipt)
        free = dict(receipt)
        free["payment_id"] = None
        skipped = await client.post("/api/envelope/verify", json=free)

    ok_body = json.loads(ok.text)
    skipped_body = json.loads(skipped.text)
    assert ok_body["verified"] is True
    assert ok_body["commerce"]["status"] == "skipped"
    assert ok_body["commerce"]["reason"] == "free_or_unpriced"
    assert skipped_body["commerce"]["status"] == "skipped"
    assert get_ledger().ledger_entries() == []
