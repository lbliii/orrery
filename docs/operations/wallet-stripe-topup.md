# Stripe wallet top-up (Checkout + webhook)

Paid wallet credits flow through verified Stripe webhooks only
([ADR 0003](../adr/0003-stripe-topup.md)). Checkout Session creation embeds
``metadata.owner_id``; the browser success redirect is UX only — never credits
from query params.

## Routes

| Route | Purpose |
| --- | --- |
| ``POST /api/wallet/stripe/checkout`` | Create Checkout Session (no ledger credit) |
| ``POST /api/wallet/stripe/webhook`` | Verify signature; credit ledger once per ``event.id`` |

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
