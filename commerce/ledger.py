"""In-memory prepaid wallet ledger (ADR 0002).

Local integer-cent account/hold/ledger ops with idempotent hold → capture/release.
No Stripe on the hot path — see ``commerce.stubs`` for the pre-ledger runtime.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from commerce.errors import (
    HoldNotFoundError,
    InsufficientBalanceError,
    InvalidHoldTransitionError,
)

DEFAULT_HOLD_TTL = timedelta(minutes=30)


class LedgerOp(StrEnum):
    CREDIT = "credit"
    HOLD = "hold"
    CAPTURE = "capture"
    RELEASE = "release"
    DEBIT = "debit"


class HoldStatus(StrEnum):
    OPEN = "open"
    CAPTURED = "captured"
    RELEASED = "released"
    EXPIRED = "expired"


@dataclass(frozen=True)
class WalletAccount:
    owner_id: str
    balance_cents: int
    held_cents: int
    currency: str = "usd"
    stripe_customer_id: str | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class LedgerEntry:
    id: str
    owner_id: str
    op: LedgerOp
    amount_cents: int
    idempotency_key: str
    payment_id: str | None = None
    envelope_id: str | None = None
    skill: str | None = None
    price_per_call_cents: int | None = None
    publisher_share_cents: int | None = None
    stripe_event_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class Hold:
    hold_id: str
    owner_id: str
    amount_cents: int
    idempotency_key: str
    status: HoldStatus
    expires_at: datetime
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    skill: str | None = None
    price_per_call_cents: int | None = None


@dataclass
class _MutableAccount:
    owner_id: str
    balance_cents: int = 0
    held_cents: int = 0
    currency: str = "usd"
    stripe_customer_id: str | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class WalletLedger:
    """Thread-safe in-memory prepaid ledger."""

    def __init__(
        self,
        *,
        hold_ttl: timedelta = DEFAULT_HOLD_TTL,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._hold_ttl = hold_ttl
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = threading.Lock()
        self._accounts: dict[str, _MutableAccount] = {}
        self._holds: dict[str, Hold] = {}
        self._entries: list[LedgerEntry] = []
        self._entry_by_key_op: dict[tuple[str, LedgerOp], LedgerEntry] = {}

    def get_account(self, owner_id: str) -> WalletAccount:
        with self._lock:
            account = self._account(owner_id)
            return self._snapshot_account(account)

    def credit(
        self,
        owner_id: str,
        amount_cents: int,
        *,
        idempotency_key: str,
        stripe_event_id: str | None = None,
    ) -> LedgerEntry:
        if amount_cents <= 0:
            msg = "credit amount_cents must be positive"
            raise ValueError(msg)
        with self._lock:
            existing = self._entry_by_key_op.get((idempotency_key, LedgerOp.CREDIT))
            if existing is not None:
                return existing
            account = self._account(owner_id)
            account.balance_cents += amount_cents
            account.updated_at = self._clock()
            return self._append_entry(
                owner_id=owner_id,
                op=LedgerOp.CREDIT,
                amount_cents=amount_cents,
                idempotency_key=idempotency_key,
                stripe_event_id=stripe_event_id,
            )

    def hold(
        self,
        owner_id: str,
        amount_cents: int,
        *,
        idempotency_key: str,
        payment_id: str | None = None,
        skill: str | None = None,
        price_per_call_cents: int | None = None,
    ) -> Hold:
        if amount_cents <= 0:
            msg = "hold amount_cents must be positive"
            raise ValueError(msg)
        key = idempotency_key
        with self._lock:
            existing = self._holds.get(key)
            if existing is not None:
                return existing
            account = self._account(owner_id)
            if account.balance_cents < amount_cents:
                raise InsufficientBalanceError(
                    price_per_call_cents=amount_cents,
                    balance_cents=account.balance_cents,
                )
            now = self._clock()
            account.balance_cents -= amount_cents
            account.held_cents += amount_cents
            account.updated_at = now
            hold = Hold(
                hold_id=str(uuid.uuid4()),
                owner_id=owner_id,
                amount_cents=amount_cents,
                idempotency_key=key,
                status=HoldStatus.OPEN,
                expires_at=now + self._hold_ttl,
                created_at=now,
                skill=skill,
                price_per_call_cents=price_per_call_cents or amount_cents,
            )
            self._holds[key] = hold
            self._append_entry(
                owner_id=owner_id,
                op=LedgerOp.HOLD,
                amount_cents=amount_cents,
                idempotency_key=key,
                payment_id=payment_id or key,
                envelope_id=payment_id or key,
                skill=skill,
                price_per_call_cents=price_per_call_cents or amount_cents,
            )
            return hold

    def capture(
        self,
        owner_id: str,
        *,
        idempotency_key: str,
        publisher_share_cents: int | None = None,
    ) -> LedgerEntry:
        with self._lock:
            existing = self._entry_by_key_op.get((idempotency_key, LedgerOp.CAPTURE))
            if existing is not None:
                return existing
            hold = self._require_hold(idempotency_key)
            if hold.owner_id != owner_id:
                raise HoldNotFoundError(idempotency_key)
            if hold.status == HoldStatus.CAPTURED:
                return self._entry_by_key_op[(idempotency_key, LedgerOp.CAPTURE)]
            if hold.status != HoldStatus.OPEN:
                raise InvalidHoldTransitionError(idempotency_key, hold.status, "capture")
            account = self._account(owner_id)
            account.held_cents -= hold.amount_cents
            account.updated_at = self._clock()
            self._holds[idempotency_key] = Hold(
                hold_id=hold.hold_id,
                owner_id=hold.owner_id,
                amount_cents=hold.amount_cents,
                idempotency_key=hold.idempotency_key,
                status=HoldStatus.CAPTURED,
                expires_at=hold.expires_at,
                created_at=hold.created_at,
                skill=hold.skill,
                price_per_call_cents=hold.price_per_call_cents,
            )
            return self._append_entry(
                owner_id=owner_id,
                op=LedgerOp.CAPTURE,
                amount_cents=hold.amount_cents,
                idempotency_key=idempotency_key,
                payment_id=idempotency_key,
                envelope_id=idempotency_key,
                skill=hold.skill,
                price_per_call_cents=hold.price_per_call_cents,
                publisher_share_cents=publisher_share_cents,
            )

    def release(
        self,
        owner_id: str,
        *,
        idempotency_key: str,
    ) -> LedgerEntry:
        with self._lock:
            existing = self._entry_by_key_op.get((idempotency_key, LedgerOp.RELEASE))
            if existing is not None:
                return existing
            hold = self._require_hold(idempotency_key)
            if hold.owner_id != owner_id:
                raise HoldNotFoundError(idempotency_key)
            if hold.status == HoldStatus.RELEASED:
                return self._entry_by_key_op[(idempotency_key, LedgerOp.RELEASE)]
            if hold.status != HoldStatus.OPEN:
                raise InvalidHoldTransitionError(idempotency_key, hold.status, "release")
            account = self._account(owner_id)
            account.held_cents -= hold.amount_cents
            account.balance_cents += hold.amount_cents
            account.updated_at = self._clock()
            self._holds[idempotency_key] = Hold(
                hold_id=hold.hold_id,
                owner_id=hold.owner_id,
                amount_cents=hold.amount_cents,
                idempotency_key=hold.idempotency_key,
                status=HoldStatus.RELEASED,
                expires_at=hold.expires_at,
                created_at=hold.created_at,
                skill=hold.skill,
                price_per_call_cents=hold.price_per_call_cents,
            )
            return self._append_entry(
                owner_id=owner_id,
                op=LedgerOp.RELEASE,
                amount_cents=hold.amount_cents,
                idempotency_key=idempotency_key,
                payment_id=idempotency_key,
                envelope_id=idempotency_key,
                skill=hold.skill,
                price_per_call_cents=hold.price_per_call_cents,
            )

    def expire_open_holds(self, *, before: datetime | None = None) -> list[Hold]:
        """Transition expired open holds to ``expired`` (same as release)."""
        cutoff = before or self._clock()
        expired: list[Hold] = []
        with self._lock:
            for key, hold in list(self._holds.items()):
                if hold.status != HoldStatus.OPEN or hold.expires_at > cutoff:
                    continue
                account = self._account(hold.owner_id)
                account.held_cents -= hold.amount_cents
                account.balance_cents += hold.amount_cents
                account.updated_at = self._clock()
                terminal = Hold(
                    hold_id=hold.hold_id,
                    owner_id=hold.owner_id,
                    amount_cents=hold.amount_cents,
                    idempotency_key=hold.idempotency_key,
                    status=HoldStatus.EXPIRED,
                    expires_at=hold.expires_at,
                    created_at=hold.created_at,
                    skill=hold.skill,
                    price_per_call_cents=hold.price_per_call_cents,
                )
                self._holds[key] = terminal
                self._append_entry(
                    owner_id=hold.owner_id,
                    op=LedgerOp.RELEASE,
                    amount_cents=hold.amount_cents,
                    idempotency_key=key,
                    payment_id=key,
                    envelope_id=key,
                    skill=hold.skill,
                    price_per_call_cents=hold.price_per_call_cents,
                )
                expired.append(terminal)
        return expired

    def ledger_entries(self, owner_id: str | None = None) -> list[LedgerEntry]:
        with self._lock:
            if owner_id is None:
                return list(self._entries)
            return [entry for entry in self._entries if entry.owner_id == owner_id]

    def _account(self, owner_id: str) -> _MutableAccount:
        account = self._accounts.get(owner_id)
        if account is None:
            account = _MutableAccount(owner_id=owner_id)
            self._accounts[owner_id] = account
        return account

    def _snapshot_account(self, account: _MutableAccount) -> WalletAccount:
        return WalletAccount(
            owner_id=account.owner_id,
            balance_cents=account.balance_cents,
            held_cents=account.held_cents,
            currency=account.currency,
            stripe_customer_id=account.stripe_customer_id,
            updated_at=account.updated_at,
        )

    def _require_hold(self, idempotency_key: str) -> Hold:
        hold = self._holds.get(idempotency_key)
        if hold is None:
            raise HoldNotFoundError(idempotency_key)
        return hold

    def _append_entry(
        self,
        *,
        owner_id: str,
        op: LedgerOp,
        amount_cents: int,
        idempotency_key: str,
        payment_id: str | None = None,
        envelope_id: str | None = None,
        skill: str | None = None,
        price_per_call_cents: int | None = None,
        publisher_share_cents: int | None = None,
        stripe_event_id: str | None = None,
    ) -> LedgerEntry:
        entry = LedgerEntry(
            id=str(uuid.uuid4()),
            owner_id=owner_id,
            op=op,
            amount_cents=amount_cents,
            idempotency_key=idempotency_key,
            payment_id=payment_id,
            envelope_id=envelope_id,
            skill=skill,
            price_per_call_cents=price_per_call_cents,
            publisher_share_cents=publisher_share_cents,
            stripe_event_id=stripe_event_id,
            created_at=self._clock(),
        )
        self._entries.append(entry)
        self._entry_by_key_op[(idempotency_key, op)] = entry
        return entry
