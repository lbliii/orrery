# ADR 0002: Prepaid wallet ledger (hold / capture on verify)

- **Status:** Design accepted (implementation unblocked)
- **Date:** 2026-08-08
- **Issue:** [#38](https://github.com/lbliii/orrery/issues/38)
- **Parent epic:** [#9](https://github.com/lbliii/orrery/issues/9) Trust & Commerce
- **Depends on:** [0001](./0001-control-plane-wallet.md); Wave 0 pointing loop + Wave 1 reactive star green before code

## Context

Commerce stubs (#35) log charge/refund only. Wave 2 needs an **internal
prepaid ledger** in integer cents so Orrery can soft-hold at call and commit
debit only when an Envelope verifies — without Stripe on the hot path.

## Non-goals

- Per-call card authorization / Stripe micropayments
- Orrery as an execution proxy for publisher tools
- Publisher payouts (Wave 5); optional share column only
- Opening an implementation issue until Wave 0+1 exit (or explicit unblock)

## Schema (logical)

### `wallet_accounts`

| Column | Type | Notes |
| --- | --- | --- |
| `owner_id` | string | User or org id (Orrery tenancy) |
| `balance_cents` | int | Available balance (not held) |
| `held_cents` | int | Sum of open holds |
| `currency` | string | `usd` only in MVP |
| `stripe_customer_id` | string? | Mapped in [0003](./0003-stripe-topup.md) |
| `updated_at` | timestamp | |

Invariant: `balance_cents >= 0`, `held_cents >= 0`. Spendable = `balance_cents`.

### `wallet_ledger_entries`

Append-only ops:

| `op` | Meaning |
| --- | --- |
| `credit` | Top-up (Stripe webhook only) |
| `hold` | Soft reserve at call time |
| `capture` | Commit hold → burn on verify-ok |
| `release` | Free hold on forge / fail / TTL |
| `debit` | Optional direct burn (prefer hold→capture) |

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid | Row id |
| `owner_id` | string | |
| `op` | enum | above |
| `amount_cents` | int | Always positive |
| `idempotency_key` | string | **Envelope id** (or `payment_id` tied 1:1) |
| `envelope_id` / `payment_id` | string | Commerce attachment on Envelope |
| `skill` | string? | Resolve name |
| `price_per_call_cents` | int? | Snapshot at hold |
| `publisher_share_cents` | int? | Optional accrual for Wave 5; **no payouts now** |
| `stripe_event_id` | string? | For `credit` only |
| `created_at` | timestamp | |

### Holds

| Column | Type | Notes |
| --- | --- | --- |
| `hold_id` | uuid | |
| `owner_id` | string | |
| `amount_cents` | int | |
| `idempotency_key` | string | Envelope / payment id |
| `status` | enum | `open` / `captured` / `released` / `expired` |
| `expires_at` | timestamp | Hold TTL (e.g. 15–60 min; tune in impl) |
| `created_at` | timestamp | |

## Idempotency

- Primary key for call-path ops: **Envelope id** (stable `payment_id` minted at
  call / hold time and carried on the Envelope receipt).
- Replaying verify with the same Envelope id must not double-capture.
- Replaying hold with the same key returns the existing open hold.
- Stripe credits use **Stripe event id** as idempotency (see 0003).

## Concurrency

- Account updates under row lock / compare-and-swap on `(balance_cents, held_cents)`.
- Double-call with distinct Envelope ids → two holds if balance allows.
- Double-call / replay with same Envelope id → idempotent single hold.
- Capture/release only transition `open` → terminal; races lose via status check.

## Insufficient balance

MCP / HTTP error shape (no Stripe call):

```json
{
  "code": "insufficient_balance",
  "price_per_call": "$0.02",
  "price_per_call_cents": 2,
  "balance": "$1.00",
  "balance_cents": 100,
  "top_up_url": "https://orrery.lol/wallet/top-up"
}
```

Resolve stays fast and never blocks on payment-provider health.

## State machine

```text
credit  → balance += amount
hold    → if balance >= price: balance -= price; held += price; else insufficient_balance
capture → held -= price  (burn; optional publisher_share_cents accrual)
release → held -= price; balance += price
TTL     → same as release when expires_at passes
```

## Sequence: call → hold → verify → capture / release

```mermaid
sequenceDiagram
  participant Agent
  participant Publisher as Publisher MCP
  participant Orrery as Orrery control plane
  participant Ledger as Prepaid ledger

  Agent->>Orrery: resolve(name)
  Orrery-->>Agent: endpoint, digest, key, price_per_call
  Agent->>Orrery: hold(price, payment_id=Envelope id)
  alt insufficient
    Orrery-->>Agent: insufficient_balance + top_up_url
  else ok
    Orrery->>Ledger: hold (idempotent on Envelope id)
    Ledger-->>Orrery: hold open
    Orrery-->>Agent: payment_id
    Agent->>Publisher: tools/call (direct; not proxied)
    Publisher-->>Agent: signed Envelope (+ payment_id)
    Agent->>Orrery: POST /api/envelope/verify
    alt verify ok
      Orrery->>Ledger: capture(payment_id)
      Orrery-->>Agent: verified=true
    else forge / fail
      Orrery->>Ledger: release(payment_id)
      Orrery-->>Agent: verified=false
    end
  end
```

## Hot path rule

Balance / hold / capture / release are **local ledger ops**. Never call Stripe
on resolve, hold, or verify.

## Implementation gate

Do **not** open an implementation issue until Wave 0+1 exit (or explicit
unblock). Stubs in `commerce.stubs` remain the runtime behavior until then.
