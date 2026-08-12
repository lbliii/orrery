# Stripe wallet top-up (Checkout + webhook)

Paid wallet credits flow through verified Stripe webhooks only
([ADR 0003](../adr/0003-stripe-topup.md)). Checkout Session creation embeds
``metadata.owner_id``; the browser success redirect is UX only — never credits
from query params.

## Routes

| Route | Purpose |
| --- | --- |
| ``GET /wallet/top-up`` | Public top-up page — balance + fixed Checkout packs |
| ``GET /wallet`` | Checkout return UX (``?topup=success`` / ``?topup=cancel``); no credit from URL |
| ``POST /api/wallet/stripe/checkout`` | Create Checkout Session (no ledger credit) |
| ``POST /api/wallet/stripe/webhook`` | Verify signature; credit ledger once per ``event.id`` |

## UX

- **Top-up page** (``/wallet/top-up``): shows spendable balance when
  ``owner_id`` is supplied; CTA posts to Checkout with a fixed pack
  (``starter`` / ``standard`` / ``premium``). No per-call Stripe on this
  surface.
- **Success/cancel** (``/wallet?topup=…``): browser redirect only. Balance
  changes after webhook credit — never from query params.
- **`insufficient_balance`**: verify/hold errors include ``top_up_url`` pointing
  at ``https://orrery.lol/wallet/top-up`` (see ADR 0002).

## Environment

| Variable | Required | Notes |
| --- | --- | --- |
| ``STRIPE_SECRET_KEY`` | Checkout create | Stripe REST; not used in pytest |
| ``STRIPE_WEBHOOK_SECRET`` | Webhook verify | Endpoint signing secret |
| ``ORRERY_WALLET_ENABLED`` | Ledger wiring | Same flag as verify capture/release |
| ``ORRERY_PUBLIC_ORIGIN`` | Checkout URLs | Default success/cancel under ``/wallet`` |

## Packs (cents)

| Pack key | Amount |
| --- | --- |
| ``starter`` | 500 ($5) |
| ``standard`` | 2000 ($20) |
| ``premium`` | 10000 ($100) |

Amount credited always comes from the Stripe session object
(``amount_total``), never from client POST bodies.

## Test doubles

``commerce.stripe_topup.configure_stripe_topup`` accepts injectable webhook
verifiers and Checkout clients so CI needs no live Stripe secrets. Tests sign
fixtures with ``sign_test_webhook`` using the same HMAC algorithm as production.

## Acceptance

```bash
uv run pytest tests/test_stripe_topup.py -q
uv run ruff check .
```
