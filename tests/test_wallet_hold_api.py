"""Wallet hold HTTP API (ADR 0002, #377)."""

from __future__ import annotations

import json

import pytest
from chirp.testing import TestClient

from commerce import get_ledger, reset_ledger
from commerce.errors import TOP_UP_URL
from commerce.ledger import HoldStatus, LedgerOp

OWNER = "user-hold-1"
PAYMENT_ID = "pay-hold-api"
PRICE = "$0.02"
PRICE_CENTS = 2


@pytest.fixture
def wallet_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORRERY_WALLET_ENABLED", "1")
    reset_ledger()


def _hold_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "owner_id": OWNER,
        "payment_id": PAYMENT_ID,
        "price_per_call": PRICE,
        "skill": "html-to-pdf",
    }
    payload.update(overrides)
    return payload


@pytest.mark.issue(377)
async def test_hold_succeeds_when_balance_allows(
    wallet_enabled: None, example_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    get_ledger().credit(OWNER, 100, idempotency_key="credit-hold-api")

    async with TestClient(example_app) as client:
        response = await client.post("/api/wallet/hold", json=_hold_payload())

    assert response.status == 200
    body = json.loads(response.text)
    assert body["status"] == HoldStatus.OPEN
    assert body["hold_status"] == HoldStatus.OPEN
    assert body["payment_id"] == PAYMENT_ID
    assert body["owner_id"] == OWNER
    assert body["amount_cents"] == PRICE_CENTS
    assert body["price_per_call_cents"] == PRICE_CENTS

    account = get_ledger().get_account(OWNER)
    assert account.balance_cents == 98
    assert account.held_cents == PRICE_CENTS


@pytest.mark.issue(377)
async def test_insufficient_balance_structured_error(
    wallet_enabled: None, example_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    async with TestClient(example_app) as client:
        response = await client.post("/api/wallet/hold", json=_hold_payload())

    assert response.status == 402
    body = json.loads(response.text)
    assert body["code"] == "insufficient_balance"
    assert body["price_per_call_cents"] == PRICE_CENTS
    assert body["balance_cents"] == 0
    assert body["top_up_url"] == TOP_UP_URL
    assert get_ledger().ledger_entries() == []


@pytest.mark.issue(377)
async def test_replay_same_key_returns_existing_open_hold(
    wallet_enabled: None, example_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    get_ledger().credit(OWNER, 100, idempotency_key="credit-hold-replay")

    async with TestClient(example_app) as client:
        first = await client.post("/api/wallet/hold", json=_hold_payload())
        second = await client.post("/api/wallet/hold", json=_hold_payload())

    assert first.status == 200
    assert second.status == 200
    first_body = json.loads(first.text)
    second_body = json.loads(second.text)
    assert first_body["hold_id"] == second_body["hold_id"]
    assert first_body["hold_status"] == HoldStatus.OPEN
    assert second_body["hold_status"] == HoldStatus.OPEN

    hold_entries = [
        entry for entry in get_ledger().ledger_entries(OWNER) if entry.op == LedgerOp.HOLD
    ]
    assert len(hold_entries) == 1
    account = get_ledger().get_account(OWNER)
    assert account.balance_cents == 98
    assert account.held_cents == PRICE_CENTS


@pytest.mark.issue(377)
async def test_wallet_disabled_returns_flag(
    example_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ORRERY_WALLET_ENABLED", raising=False)
    reset_ledger()

    async with TestClient(example_app) as client:
        response = await client.post("/api/wallet/hold", json=_hold_payload())

    assert response.status == 503
    body = json.loads(response.text)
    assert body["error"] == "wallet_disabled"
    assert body["wallet_enabled"] is False
    assert get_ledger().ledger_entries() == []


@pytest.mark.issue(377)
async def test_hold_then_verify_capture_without_seed(
    wallet_enabled: None, example_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dogfood import signed_convert_receipt

    get_ledger().credit(OWNER, 100, idempotency_key="credit-hold-verify")

    async with TestClient(example_app) as client:
        hold = await client.post("/api/wallet/hold", json=_hold_payload())
        assert hold.status == 200

        receipt, _ = signed_convert_receipt()
        receipt["payment_id"] = PAYMENT_ID
        receipt["price_per_call"] = PRICE
        receipt["owner_id"] = OWNER
        verify = await client.post("/api/envelope/verify", json=receipt)

    assert verify.status == 200
    verify_body = json.loads(verify.text)
    assert verify_body["verified"] is True
    assert verify_body["commerce"]["status"] == "captured"

    hold_record = get_ledger().find_hold(PAYMENT_ID)
    assert hold_record is not None
    assert hold_record.status == HoldStatus.CAPTURED
    assert get_ledger().get_account(OWNER).balance_cents == 98
