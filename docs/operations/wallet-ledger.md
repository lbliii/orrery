# Prepaid wallet ledger (local)

In-memory integer-cent ledger implementing [ADR 0002](../adr/0002-prepaid-wallet-ledger.md)
hold → capture/release without Stripe on the hot path.

## Module

```python
from commerce.ledger import WalletLedger
from commerce.errors import InsufficientBalanceError
```

``commerce.stubs`` remains the runtime hook until verify wiring (leaf #2) swaps
call sites to this ledger.

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
uv run pytest tests/test_wallet_ledger.py -q
uv run ruff check .
```
