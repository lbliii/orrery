# Prepaid wallet ledger (local)

In-memory integer-cent ledger implementing [ADR 0002](../adr/0002-prepaid-wallet-ledger.md)
hold → capture/release without Stripe on the hot path.

## Module

```python
from commerce.ledger import WalletLedger
from commerce.errors import InsufficientBalanceError
from commerce import charge_on_verify, refund_on_forge, wallet_enabled
```

When ``ORRERY_WALLET_ENABLED=1``, ``POST /api/envelope/verify`` captures or
releases via the ledger. Otherwise loud stubs in ``commerce.stubs`` remain.

## Hold sequence

Agents open a prepaid hold **before** calling the publisher (ADR 0002):

```text
POST /api/wallet/hold  (idempotent on payment_id)
  → publisher tools/call
  → POST /api/envelope/verify  (capture or release)
```

| Step | Endpoint | Ledger op |
| --- | --- | --- |
| Call time | ``POST /api/wallet/hold`` | ``hold`` (soft reserve) |
| Verify ok | ``POST /api/envelope/verify`` | ``capture`` |
| Forge / fail | ``POST /api/envelope/verify`` | ``release`` |

Request body (machine clients — CSRF exempt):

```json
{
  "owner_id": "user-abc",
  "payment_id": "env-envelope-id",
  "price_per_call": "$0.02",
  "skill": "html-to-pdf"
}
```

``payment_id`` must match the Envelope id carried on the receipt. ``skill`` may
substitute catalog ``price_per_call`` when omitted. ``amount_cents`` is an
alternate to ``price_per_call``.

Success (``200``): open hold payload with ``hold_id``, ``hold_status: open``,
``expires_at``. Replay with the same ``payment_id`` returns the existing open
hold — no double reserve.

Insufficient balance (``402``): ADR 0002 JSON (``code: insufficient_balance``,
``top_up_url``).

Wallet disabled (``503``): ``{"error": "wallet_disabled", "wallet_enabled": false}``
— no ledger touch; enable ``ORRERY_WALLET_ENABLED=1`` for real holds.

Never calls Stripe on the hold path.

## Verify sequence

Envelope verify is the commit point for prepaid tolls (ADR 0002):

```text
hold (call time, idempotent on payment_id)
  → verify ok  → capture(payment_id)
  → forge/fail → release(payment_id)
```

| Verify outcome | Ledger op | Free / null price |
| --- | --- | --- |
| ``verified=true`` | ``capture`` | skipped (no ledger touch) |
| ``verified=false`` | ``release`` | skipped (no ledger touch) |

Replay of verify with the same ``payment_id`` returns the existing capture or
release row — no double burn.

Optional receipt fields (not part of the Envelope signature):

- ``payment_id`` — idempotency key / hold key (1:1 with Envelope id)
- ``price_per_call`` — toll label; parsed to cents for paid paths
- ``owner_id`` — wallet account; defaults to the hold's owner when omitted

Feature flag: ``ORRERY_WALLET_ENABLED=1`` (or ``true`` / ``yes``).

## State machine

| Op | Account effect |
| --- | --- |
| ``credit`` | ``balance += amount`` |
| ``hold`` | ``balance -= price``; ``held += price`` (or ``insufficient_balance``) |
| ``capture`` | ``held -= price`` (burn) |
| ``release`` | ``held -= price``; ``balance += price`` |
| TTL | ``expire_open_holds()`` — same as release when ``expires_at`` passes |

Default hold TTL: **30 minutes**.

## Idempotency keys

| Op | Key |
| --- | --- |
| ``hold`` / ``capture`` / ``release`` | Envelope id / ``payment_id`` (1:1) |
| ``credit`` | Stripe ``event.id`` (future top-up leaf) |

Replaying the same key returns the existing hold or ledger row — no double
capture or double hold.

## Insufficient balance

``hold`` raises ``InsufficientBalanceError`` with ADR 0002 JSON shape:

```json
{
  "code": "insufficient_balance",
  "price_per_call": "$0.02",
  "price_per_call_cents": 2,
  "balance": "$0.00",
  "balance_cents": 0,
  "top_up_url": "https://orrery.lol/wallet/top-up"
}
```

No network calls on resolve, hold, or verify paths.

## Acceptance

```bash
uv run pytest tests/test_wallet_hold_api.py tests/test_wallet_verify_wire.py tests/test_wallet_ledger.py -q
uv run ruff check .
```
