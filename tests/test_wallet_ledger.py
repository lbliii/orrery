"""Prepaid wallet ledger domain (ADR 0002, #369)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from commerce.errors import InsufficientBalanceError
from commerce.ledger import HoldStatus, LedgerOp, WalletLedger

OWNER = "user-1"
PAYMENT_ID = "env-abc123"
PRICE_CENTS = 2


@pytest.fixture
def ledger() -> WalletLedger:
    return WalletLedger()


@pytest.mark.issue(369)
def test_credit_hold_capture_state_machine(ledger: WalletLedger) -> None:
    ledger.credit(OWNER, 100, idempotency_key="stripe_evt_1", stripe_event_id="stripe_evt_1")

    hold = ledger.hold(
        OWNER,
        PRICE_CENTS,
        idempotency_key=PAYMENT_ID,
        payment_id=PAYMENT_ID,
        skill="orrery/world-time",
        price_per_call_cents=PRICE_CENTS,
    )
    assert hold.status == HoldStatus.OPEN

    account = ledger.get_account(OWNER)
    assert account.balance_cents == 98
    assert account.held_cents == PRICE_CENTS

    capture = ledger.capture(OWNER, idempotency_key=PAYMENT_ID)
    assert capture.op == LedgerOp.CAPTURE

    settled = ledger.get_account(OWNER)
    assert settled.balance_cents == 98
    assert settled.held_cents == 0
    assert ledger._holds[PAYMENT_ID].status == HoldStatus.CAPTURED


@pytest.mark.issue(369)
def test_credit_hold_release_state_machine(ledger: WalletLedger) -> None:
    ledger.credit(OWNER, 100, idempotency_key="stripe_evt_2", stripe_event_id="stripe_evt_2")

    ledger.hold(OWNER, PRICE_CENTS, idempotency_key=PAYMENT_ID, payment_id=PAYMENT_ID)

    mid = ledger.get_account(OWNER)
    assert mid.balance_cents == 98
    assert mid.held_cents == PRICE_CENTS

    release = ledger.release(OWNER, idempotency_key=PAYMENT_ID)
    assert release.op == LedgerOp.RELEASE

    restored = ledger.get_account(OWNER)
    assert restored.balance_cents == 100
    assert restored.held_cents == 0
    assert ledger._holds[PAYMENT_ID].status == HoldStatus.RELEASED


@pytest.mark.issue(369)
def test_idempotent_hold_replay(ledger: WalletLedger) -> None:
    ledger.credit(OWNER, 100, idempotency_key="stripe_evt_3", stripe_event_id="stripe_evt_3")

    first = ledger.hold(OWNER, PRICE_CENTS, idempotency_key=PAYMENT_ID, payment_id=PAYMENT_ID)
    second = ledger.hold(OWNER, PRICE_CENTS, idempotency_key=PAYMENT_ID, payment_id=PAYMENT_ID)

    assert first.hold_id == second.hold_id
    account = ledger.get_account(OWNER)
    assert account.balance_cents == 98
    assert account.held_cents == PRICE_CENTS
    hold_entries = [e for e in ledger.ledger_entries(OWNER) if e.op == LedgerOp.HOLD]
    assert len(hold_entries) == 1


@pytest.mark.issue(369)
def test_idempotent_capture_replay(ledger: WalletLedger) -> None:
    ledger.credit(OWNER, 100, idempotency_key="stripe_evt_4", stripe_event_id="stripe_evt_4")
    ledger.hold(OWNER, PRICE_CENTS, idempotency_key=PAYMENT_ID, payment_id=PAYMENT_ID)

    first = ledger.capture(OWNER, idempotency_key=PAYMENT_ID)
    second = ledger.capture(OWNER, idempotency_key=PAYMENT_ID)

    assert first.id == second.id
    settled = ledger.get_account(OWNER)
    assert settled.balance_cents == 98
    assert settled.held_cents == 0
    capture_entries = [e for e in ledger.ledger_entries(OWNER) if e.op == LedgerOp.CAPTURE]
    assert len(capture_entries) == 1


@pytest.mark.issue(369)
def test_idempotent_release_replay(ledger: WalletLedger) -> None:
    ledger.credit(OWNER, 100, idempotency_key="stripe_evt_5", stripe_event_id="stripe_evt_5")
    ledger.hold(OWNER, PRICE_CENTS, idempotency_key=PAYMENT_ID, payment_id=PAYMENT_ID)

    first = ledger.release(OWNER, idempotency_key=PAYMENT_ID)
    second = ledger.release(OWNER, idempotency_key=PAYMENT_ID)

    assert first.id == second.id
    restored = ledger.get_account(OWNER)
    assert restored.balance_cents == 100
    assert restored.held_cents == 0
    release_entries = [e for e in ledger.ledger_entries(OWNER) if e.op == LedgerOp.RELEASE]
    assert len(release_entries) == 1


@pytest.mark.issue(369)
def test_insufficient_balance_error_shape(ledger: WalletLedger) -> None:
    with pytest.raises(InsufficientBalanceError) as exc_info:
        ledger.hold(OWNER, PRICE_CENTS, idempotency_key=PAYMENT_ID, payment_id=PAYMENT_ID)

    payload = exc_info.value.to_dict()
    assert payload == {
        "code": "insufficient_balance",
        "price_per_call": "$0.02",
        "price_per_call_cents": 2,
        "balance": "$0.00",
        "balance_cents": 0,
        "top_up_url": "https://orrery.lol/wallet/top-up",
    }


@pytest.mark.issue(369)
def test_credit_idempotency(ledger: WalletLedger) -> None:
    first = ledger.credit(
        OWNER, 500, idempotency_key="stripe_evt_6", stripe_event_id="stripe_evt_6"
    )
    second = ledger.credit(
        OWNER, 500, idempotency_key="stripe_evt_6", stripe_event_id="stripe_evt_6"
    )

    assert first.id == second.id
    assert ledger.get_account(OWNER).balance_cents == 500


@pytest.mark.issue(369)
def test_hold_ttl_expires_like_release() -> None:
    start = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
    clock = {"now": start}
    ledger = WalletLedger(
        hold_ttl=timedelta(minutes=15),
        clock=lambda: clock["now"],
    )
    ledger.credit(OWNER, 100, idempotency_key="stripe_evt_7", stripe_event_id="stripe_evt_7")
    ledger.hold(OWNER, PRICE_CENTS, idempotency_key=PAYMENT_ID, payment_id=PAYMENT_ID)

    clock["now"] = start + timedelta(minutes=16)
    expired = ledger.expire_open_holds()

    assert len(expired) == 1
    assert expired[0].status == HoldStatus.EXPIRED
    account = ledger.get_account(OWNER)
    assert account.balance_cents == 100
    assert account.held_cents == 0
