# ADR 0003: Stripe $5 top-up (Checkout + webhook credit)

- **Status:** Design accepted (implementation gated)
- **Date:** 2026-08-08
- **Issue:** [#39](https://github.com/lbliii/orrery/issues/39)
- **Parent epic:** [#9](https://github.com/lbliii/orrery/issues/9) Trust & Commerce
- **Depends on:** [0002](./0002-prepaid-wallet-ledger.md) ledger design; Wave 0+1 green

## Context

The prepaid ledger needs a funding path. Strategy ([0001](./0001-control-plane-wallet.md)):
**Stripe top-up only** — never per-call charges. MVP amount is **$5**; optional
larger packs (`$20` / `$100`) may share the same flow.

## Non-goals (this design / Wave 2)

- Stripe SDK or webhook code in product until ledger design is accepted and
  Wave 0+1 are green
- Per-call PaymentIntents / micropayments
- Trusting the browser/client “I paid” claim
- Customer Portal / auto-reload (optional later)

## Flow (end-to-end)

```mermaid
sequenceDiagram
  participant User
  participant Orrery as Orrery UI/API
  participant Stripe
  participant Ledger as Prepaid ledger

  User->>Orrery: Start top-up ($5 / $20 / $100)
  Orrery->>Stripe: Create Checkout Session<br/>(amount, customer, metadata.owner_id)
  Stripe-->>User: Checkout UI
  User->>Stripe: Pay
  Stripe->>Orrery: webhook checkout.session.completed<br/>(or payment_intent.succeeded)
  Note over Orrery: Verify signature; idempotent on event.id
  Orrery->>Ledger: credit(owner_id, amount_cents, stripe_event_id)
  Ledger-->>Orrery: balance updated (or duplicate no-op)
  Orrery-->>User: Wallet shows new balance
```

### Mapping

- Stripe **Customer** ↔ Orrery `wallet_accounts.owner_id` via
  `stripe_customer_id`.
- Checkout Session `metadata` must include `owner_id` (+ optional `pack`).
- Success/cancel URLs return to Orrery wallet UI; UI may poll balance but
  **must not** credit from query params.

## Webhook verification + idempotency

1. Verify Stripe-Signature with endpoint secret (raw body).
2. Accept only known event types for credit:
   - `checkout.session.completed` (preferred for Checkout)
   - optionally `payment_intent.succeeded` if used without double-credit
3. Idempotency key = **Stripe `event.id`** stored on ledger `credit` rows
   (`stripe_event_id`). Duplicate delivery → no second credit.
4. Amount comes from Stripe object (session/payment), not client POST body.
5. Reject / ignore events that lack a resolvable `owner_id` mapping.

**Never trust client “I paid.”** Client success redirect is UX only.

## Failure modes

| Mode | Handling |
| --- | --- |
| Abandoned Checkout | No webhook → no credit; hold balance unchanged |
| Duplicate webhook | Idempotent on `event.id` → single credit |
| Signature fail / replay with bad sig | 4xx; no credit |
| Paid but metadata missing `owner_id` | Alert + manual reconcile; do not guess owner |
| Double event types for one payment | Single credit path; second op sees same business key or is ignored |
| Ledger down during webhook | Return 5xx so Stripe retries; keep handler idempotent |
| User refreshes success URL | No credit from URL; show current ledger balance |

## Amounts (MVP)

| Pack | Cents |
| --- | --- |
| Starter | 500 ($5) |
| Optional | 2000 ($20), 10000 ($100) |

Starter grant policy (product): new wallets may receive a one-time $5 promo
credit **without** Stripe; paid top-ups always go through Checkout + webhook.

## Implementation gate

No Stripe SDK, Checkout Session creation, or webhook route in product PRs
until:

1. Ledger design (#38 / ADR 0002) accepted
2. Wave 0+1 exit signals green
3. Explicit implementation issue opened

This document satisfies the **written design** acceptance for #39.
