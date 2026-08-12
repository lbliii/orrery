"""Stripe Checkout top-up → prepaid ledger credit (ADR 0003)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from commerce.ledger import LedgerOp, WalletLedger
from commerce.verify_wire import get_ledger

logger = logging.getLogger("orrery.commerce")

TOPUP_PACKS: dict[str, int] = {
    "starter": 500,
    "standard": 2000,
    "premium": 10000,
}
DEFAULT_PACK = "starter"
_CREDIT_EVENT_TYPES = frozenset({"checkout.session.completed"})


class WebhookVerificationError(Exception):
    """Stripe webhook signature or payload could not be verified."""


@dataclass(frozen=True)
class StripeEvent:
    id: str
    type: str
    data: dict[str, Any]


@dataclass(frozen=True)
class WebhookResult:
    status: str
    reason: str | None = None
    entry_id: str | None = None
    owner_id: str | None = None
    amount_cents: int | None = None


@dataclass(frozen=True)
class CheckoutSessionRequest:
    owner_id: str
    pack: str = DEFAULT_PACK
    success_url: str = ""
    cancel_url: str = ""


class StripeWebhookVerifier(Protocol):
    def verify(self, payload: bytes, signature_header: str, secret: str) -> StripeEvent: ...


class StripeCheckoutClient(Protocol):
    def create_session(
        self, request: CheckoutSessionRequest, *, amount_cents: int
    ) -> dict[str, Any]: ...


class HmacStripeWebhookVerifier:
    """Verify Stripe-Signature headers without the Stripe SDK."""

    def __init__(self, *, tolerance_seconds: int = 300) -> None:
        self._tolerance_seconds = tolerance_seconds

    def verify(self, payload: bytes, signature_header: str, secret: str) -> StripeEvent:
        if not signature_header.strip():
            msg = "missing Stripe-Signature header"
            raise WebhookVerificationError(msg)
        parts = _parse_signature_header(signature_header)
        timestamps = parts.get("t")
        signatures = parts.get("v1")
        if not timestamps or not signatures:
            msg = "malformed Stripe-Signature header"
            raise WebhookVerificationError(msg)
        timestamp = int(timestamps[0])
        now = int(time.time())
        if abs(now - timestamp) > self._tolerance_seconds:
            msg = "timestamp outside tolerance"
            raise WebhookVerificationError(msg)
        signed_payload = f"{timestamp}.".encode() + payload
        expected = hmac.new(
            secret.encode("utf-8"),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()
        if not any(hmac.compare_digest(expected, sig) for sig in signatures):
            msg = "invalid signature"
            raise WebhookVerificationError(msg)
        try:
            raw = json.loads(payload)
        except json.JSONDecodeError as exc:
            msg = "invalid webhook JSON"
            raise WebhookVerificationError(msg) from exc
        if not isinstance(raw, dict):
            msg = "webhook payload must be an object"
            raise WebhookVerificationError(msg)
        event_id = raw.get("id")
        event_type = raw.get("type")
        data = raw.get("data")
        if not isinstance(event_id, str) or not event_id:
            msg = "missing event id"
            raise WebhookVerificationError(msg)
        if not isinstance(event_type, str) or not event_type:
            msg = "missing event type"
            raise WebhookVerificationError(msg)
        if not isinstance(data, dict):
            msg = "missing event data"
            raise WebhookVerificationError(msg)
        return StripeEvent(id=event_id, type=event_type, data=data)


class RestStripeCheckoutClient:
    """Create Checkout Sessions via Stripe REST (no SDK)."""

    def create_session(
        self, request: CheckoutSessionRequest, *, amount_cents: int
    ) -> dict[str, Any]:
        secret_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
        if not secret_key:
            msg = "STRIPE_SECRET_KEY is not configured"
            raise RuntimeError(msg)
        form = {
            "mode": "payment",
            "success_url": request.success_url,
            "cancel_url": request.cancel_url,
            "metadata[owner_id]": request.owner_id,
            "metadata[pack]": request.pack,
            "line_items[0][price_data][currency]": "usd",
            "line_items[0][price_data][unit_amount]": str(amount_cents),
            "line_items[0][price_data][product_data][name]": (
                f"Orrery wallet top-up ({request.pack})"
            ),
            "line_items[0][quantity]": "1",
        }
        body = urllib.parse.urlencode(form).encode("utf-8")
        req = urllib.request.Request(
            "https://api.stripe.com/v1/checkout/sessions",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {secret_key}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            msg = f"Stripe Checkout Session create failed: {exc.code} {detail}"
            raise RuntimeError(msg) from exc
        if not isinstance(payload, dict):
            msg = "Stripe Checkout Session response must be an object"
            raise RuntimeError(msg)
        return payload


_verifier: StripeWebhookVerifier | None = None
_checkout_client: StripeCheckoutClient | None = None


def configure_stripe_topup(
    *,
    verifier: StripeWebhookVerifier | None = None,
    checkout_client: StripeCheckoutClient | None = None,
) -> None:
    """Replace process-wide Stripe collaborators (tests)."""
    global _verifier, _checkout_client
    _verifier = verifier
    _checkout_client = checkout_client


def reset_stripe_topup() -> None:
    """Restore default Stripe collaborators (tests)."""
    configure_stripe_topup(verifier=None, checkout_client=None)


def get_webhook_verifier() -> StripeWebhookVerifier:
    if _verifier is not None:
        return _verifier
    return HmacStripeWebhookVerifier()


def get_checkout_client() -> StripeCheckoutClient:
    if _checkout_client is not None:
        return _checkout_client
    return RestStripeCheckoutClient()


def webhook_secret() -> str:
    return os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()


def resolve_pack(pack: str | None) -> tuple[str, int]:
    key = (pack or DEFAULT_PACK).strip().lower()
    amount = TOPUP_PACKS.get(key)
    if amount is None:
        msg = f"unknown top-up pack: {pack!r}"
        raise ValueError(msg)
    return key, amount


def default_checkout_urls() -> tuple[str, str]:
    origin = os.environ.get("ORRERY_PUBLIC_ORIGIN", "").strip().rstrip("/")
    if not origin:
        origin = "http://127.0.0.1:8000"
    return f"{origin}/wallet?topup=success", f"{origin}/wallet?topup=cancel"


def create_checkout_session(
    *,
    owner_id: str,
    pack: str | None = None,
    success_url: str | None = None,
    cancel_url: str | None = None,
) -> dict[str, Any]:
    """Start a Stripe Checkout Session with owner metadata (no ledger credit)."""
    owner = owner_id.strip()
    if not owner:
        msg = "owner_id is required"
        raise ValueError(msg)
    pack_key, amount_cents = resolve_pack(pack)
    default_success, default_cancel = default_checkout_urls()
    request = CheckoutSessionRequest(
        owner_id=owner,
        pack=pack_key,
        success_url=(success_url or default_success).strip(),
        cancel_url=(cancel_url or default_cancel).strip(),
    )
    session = get_checkout_client().create_session(request, amount_cents=amount_cents)
    metadata = session.get("metadata")
    if isinstance(metadata, dict):
        session_owner = metadata.get("owner_id")
        if session_owner != owner:
            msg = "checkout session metadata.owner_id mismatch"
            raise RuntimeError(msg)
    return session


def _find_credit_entry(ledger: WalletLedger, event_id: str):
    for entry in ledger.ledger_entries():
        if entry.op == LedgerOp.CREDIT and entry.idempotency_key == event_id:
            return entry
    return None


def process_webhook_event(
    event: StripeEvent, *, ledger: WalletLedger | None = None
) -> WebhookResult:
    """Credit the prepaid ledger for a verified Stripe webhook event."""
    store = ledger if ledger is not None else get_ledger()
    if event.type not in _CREDIT_EVENT_TYPES:
        return WebhookResult(status="ignored", reason="unsupported_event_type")

    session = event.data.get("object")
    if not isinstance(session, dict):
        return WebhookResult(status="ignored", reason="missing_session_object")

    metadata = session.get("metadata")
    owner_id = metadata.get("owner_id") if isinstance(metadata, dict) else None
    if not isinstance(owner_id, str) or not owner_id.strip():
        logger.warning("stripe.webhook missing owner_id event_id=%s", event.id)
        return WebhookResult(status="ignored", reason="missing_owner_id")

    amount_total = session.get("amount_total")
    if not isinstance(amount_total, int) or amount_total <= 0:
        return WebhookResult(status="ignored", reason="invalid_amount")

    existing = _find_credit_entry(store, event.id)
    if existing is not None:
        return WebhookResult(
            status="duplicate",
            reason="event_already_credited",
            entry_id=existing.id,
            owner_id=existing.owner_id,
            amount_cents=existing.amount_cents,
        )

    entry = store.credit(
        owner_id.strip(),
        amount_total,
        idempotency_key=event.id,
        stripe_event_id=event.id,
    )
    logger.info(
        "stripe.webhook credited owner_id=%s event_id=%s amount_cents=%s entry_id=%s",
        owner_id,
        event.id,
        amount_total,
        entry.id,
    )
    return WebhookResult(
        status="credited",
        entry_id=entry.id,
        owner_id=owner_id.strip(),
        amount_cents=amount_total,
    )


def handle_stripe_webhook(
    payload: bytes,
    *,
    signature_header: str,
    secret: str | None = None,
    ledger: WalletLedger | None = None,
) -> tuple[int, dict[str, Any]]:
    """Verify signature and apply ledger credit rules."""
    endpoint_secret = (secret if secret is not None else webhook_secret()).strip()
    if not endpoint_secret:
        return 503, {"status": "unavailable", "reason": "webhook_secret_not_configured"}
    try:
        event = get_webhook_verifier().verify(payload, signature_header, endpoint_secret)
    except WebhookVerificationError as exc:
        logger.warning("stripe.webhook verify_failed reason=%s", exc)
        return 400, {"status": "invalid", "reason": str(exc)}

    result = process_webhook_event(event, ledger=ledger)
    body: dict[str, Any] = {"status": result.status}
    if result.reason is not None:
        body["reason"] = result.reason
    if result.entry_id is not None:
        body["entry_id"] = result.entry_id
    if result.owner_id is not None:
        body["owner_id"] = result.owner_id
    if result.amount_cents is not None:
        body["amount_cents"] = result.amount_cents
    return 200, body


def sign_test_webhook(payload: bytes, *, secret: str, timestamp: int | None = None) -> str:
    """Build a Stripe-Signature header for tests (same algorithm as production)."""
    ts = int(time.time()) if timestamp is None else timestamp
    signed_payload = f"{ts}.".encode() + payload
    digest = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"


def _parse_signature_header(header: str) -> dict[str, list[str]]:
    parts: dict[str, list[str]] = {}
    for item in header.split(","):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        parts.setdefault(key.strip(), []).append(value.strip())
    return parts
