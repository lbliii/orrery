"""Stripe Checkout top-up + webhook credit (ADR 0003, #371)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import pytest
from chirp.testing import TestClient

from commerce import get_ledger, reset_ledger, reset_stripe_topup
from commerce.ledger import LedgerOp
from commerce.stripe_topup import (
    CheckoutSessionRequest,
    HmacStripeWebhookVerifier,
    StripeEvent,
    configure_stripe_topup,
    handle_stripe_webhook,
    process_webhook_event,
    sign_test_webhook,
)

OWNER = "wallet-user-371"
WEBHOOK_SECRET = "whsec_test_371"
PACK_CENTS = 500
EVENT_ID = "evt_test_checkout_completed_371"
CHECKOUT_URL = "https://checkout.stripe.test/cs_test_371"
_CSRF_RE = re.compile(r'name="_csrf_token" value="([^"]+)"')


@dataclass
class FakeCheckoutClient:
    last_request: CheckoutSessionRequest | None = None

    def create_session(
        self, request: CheckoutSessionRequest, *, amount_cents: int
    ) -> dict[str, Any]:
        self.last_request = request
        return {
            "id": "cs_test_371",
            "url": CHECKOUT_URL,
            "amount_total": amount_cents,
            "metadata": {"owner_id": request.owner_id, "pack": request.pack},
        }


def _checkout_completed_event(
    *, owner_id: str | None = OWNER, amount_total: int = PACK_CENTS
) -> bytes:
    metadata: dict[str, str] = {}
    if owner_id is not None:
        metadata["owner_id"] = owner_id
    payload = {
        "id": EVENT_ID,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_371",
                "amount_total": amount_total,
                "metadata": metadata,
            }
        },
    }
    return json.dumps(payload).encode("utf-8")


@pytest.fixture
def wallet_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORRERY_WALLET_ENABLED", "1")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)
    reset_ledger()
    reset_stripe_topup()


@pytest.fixture
def fake_checkout() -> FakeCheckoutClient:
    client = FakeCheckoutClient()
    configure_stripe_topup(checkout_client=client)
    return client


@pytest.mark.issue(371)
def test_bad_signature_rejected(wallet_enabled: None) -> None:
    payload = _checkout_completed_event()
    status, body = handle_stripe_webhook(
        payload,
        signature_header="t=1,v1=deadbeef",
    )
    assert status == 400
    assert body["status"] == "invalid"
    assert get_ledger().get_account(OWNER).balance_cents == 0


@pytest.mark.issue(371)
def test_duplicate_event_id_no_second_credit(wallet_enabled: None) -> None:
    payload = _checkout_completed_event()
    signature = sign_test_webhook(payload, secret=WEBHOOK_SECRET)
    first_status, first_body = handle_stripe_webhook(payload, signature_header=signature)
    second_status, second_body = handle_stripe_webhook(payload, signature_header=signature)

    assert first_status == 200
    assert first_body["status"] == "credited"
    assert second_status == 200
    assert second_body["status"] == "duplicate"
    assert get_ledger().get_account(OWNER).balance_cents == PACK_CENTS
    credits = [
        entry
        for entry in get_ledger().ledger_entries(OWNER)
        if entry.op == LedgerOp.CREDIT
    ]
    assert len(credits) == 1
    assert credits[0].stripe_event_id == EVENT_ID


@pytest.mark.issue(371)
def test_missing_owner_id_does_not_guess(wallet_enabled: None) -> None:
    payload = _checkout_completed_event(owner_id=None)
    signature = sign_test_webhook(payload, secret=WEBHOOK_SECRET)
    status, body = handle_stripe_webhook(payload, signature_header=signature)

    assert status == 200
    assert body["status"] == "ignored"
    assert body["reason"] == "missing_owner_id"
    assert get_ledger().ledger_entries() == []


@pytest.mark.issue(371)
def test_happy_path_fixture_credits_once(wallet_enabled: None) -> None:
    event = StripeEvent(
        id=EVENT_ID,
        type="checkout.session.completed",
        data={
            "object": {
                "amount_total": PACK_CENTS,
                "metadata": {"owner_id": OWNER, "pack": "starter"},
            }
        },
    )
    result = process_webhook_event(event)

    assert result.status == "credited"
    assert result.amount_cents == PACK_CENTS
    account = get_ledger().get_account(OWNER)
    assert account.balance_cents == PACK_CENTS
    entry = get_ledger().ledger_entries(OWNER)[0]
    assert entry.stripe_event_id == EVENT_ID
    assert entry.idempotency_key == EVENT_ID


@pytest.mark.issue(371)
def test_hmac_verifier_round_trip() -> None:
    payload = _checkout_completed_event()
    signature = sign_test_webhook(payload, secret=WEBHOOK_SECRET)
    event = HmacStripeWebhookVerifier(tolerance_seconds=3600).verify(
        payload,
        signature,
        WEBHOOK_SECRET,
    )
    assert event.id == EVENT_ID
    assert event.type == "checkout.session.completed"


@pytest.mark.issue(371)
async def test_checkout_route_includes_owner_metadata(
    wallet_enabled: None,
    fake_checkout: FakeCheckoutClient,
    example_app,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_371")
    async with TestClient(example_app) as client:
        response = await client.post(
            "/api/wallet/stripe/checkout",
            json={"owner_id": OWNER, "pack": "starter"},
        )
    assert response.status == 200
    body = json.loads(response.text)
    assert body["checkout_session_id"] == "cs_test_371"
    assert body["metadata"]["owner_id"] == OWNER
    assert fake_checkout.last_request is not None
    assert fake_checkout.last_request.owner_id == OWNER
    assert fake_checkout.last_request.pack == "starter"


@pytest.mark.issue(371)
async def test_webhook_route_rejects_bad_signature(
    wallet_enabled: None,
    example_app,
) -> None:
    payload = _checkout_completed_event()
    async with TestClient(example_app) as client:
        response = await client.post(
            "/api/wallet/stripe/webhook",
            headers={"Stripe-Signature": "t=1,v1=bad"},
            body=payload,
        )
    assert response.status == 400
    assert json.loads(response.text)["status"] == "invalid"


def _session_cookie(response) -> str:
    raw = response.header("Set-Cookie")
    assert raw, "expected chirp session cookie"
    return raw.split(";", 1)[0]


def _csrf_token(html: str) -> str:
    match = _CSRF_RE.search(html)
    assert match, "expected csrf_field on the wallet checkout form"
    return match.group(1)


async def _form_session(client: TestClient) -> tuple[str, str]:
    page = await client.get("/wallet/top-up")
    assert page.status == 200
    return _session_cookie(page), _csrf_token(page.text)


@pytest.mark.issue(433)
@pytest.mark.issue(477)
async def test_top_up_page_maps_known_checkout_errors(example_app) -> None:
    from pages.wallet._errors import KNOWN

    async with TestClient(example_app) as client:
        response = await client.get("/wallet/top-up")
        assert response.status == 200
        assert 'id="wallet-error-map"' not in response.text
        assert "walletTopUp" not in response.text
        assert "startCheckout" not in response.text
        assert "this.error = body.error" not in response.text
        for code, copy in KNOWN.items():
            landed = await client.get(f"/wallet/top-up?error={code}")
            assert landed.status == 200
            assert copy["message"] in landed.text
            assert copy["next"] in landed.text
            assert code in landed.text
            assert 'class="alert"' in landed.text
            assert 'role="alert"' in landed.text


@pytest.mark.issue(477)
async def test_top_up_form_post_redirects_to_stripe_without_js(
    wallet_enabled: None,
    fake_checkout: FakeCheckoutClient,
    example_app,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_477")
    async with TestClient(example_app) as client:
        cookie, token = await _form_session(client)
        response = await client.post(
            "/wallet/top-up",
            data={"owner_id": OWNER, "pack": "starter", "_csrf_token": token},
            headers={"Cookie": cookie},
        )
    assert response.status == 303
    assert response.header("Location") == CHECKOUT_URL
    assert fake_checkout.last_request is not None
    assert fake_checkout.last_request.owner_id == OWNER
    assert fake_checkout.last_request.pack == "starter"


@pytest.mark.issue(477)
async def test_top_up_form_htmx_sets_hx_redirect(
    wallet_enabled: None,
    fake_checkout: FakeCheckoutClient,
    example_app,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_477")
    async with TestClient(example_app) as client:
        cookie, token = await _form_session(client)
        response = await client.post(
            "/wallet/top-up",
            data={"owner_id": OWNER, "pack": "starter", "_csrf_token": token},
            headers={"Cookie": cookie, "HX-Request": "true"},
        )
    assert response.status == 200
    assert response.header("HX-Redirect") == CHECKOUT_URL
    assert fake_checkout.last_request is not None
    assert fake_checkout.last_request.owner_id == OWNER


@pytest.mark.issue(477)
async def test_top_up_form_post_maps_owner_id_required(example_app) -> None:
    from pages.wallet._errors import KNOWN

    copy = KNOWN["owner_id_required"]
    async with TestClient(example_app) as client:
        cookie, token = await _form_session(client)
        response = await client.post(
            "/wallet/top-up",
            data={"owner_id": "", "pack": "starter", "_csrf_token": token},
            headers={"Cookie": cookie},
        )
        assert response.status == 303
        location = response.header("Location")
        assert location
        assert "error=owner_id_required" in location
        landed = await client.get(location, headers={"Cookie": cookie})
    assert landed.status == 200
    assert copy["message"] in landed.text
    assert copy["next"] in landed.text
    assert "owner_id_required" in landed.text


@pytest.mark.issue(477)
async def test_top_up_form_htmx_alert_and_busy_on_invalid_pack(
    example_app,
) -> None:
    from pages.wallet._errors import KNOWN

    copy = KNOWN["invalid_pack"]
    async with TestClient(example_app) as client:
        cookie, token = await _form_session(client)
        error = await client.post(
            "/wallet/top-up",
            data={"owner_id": OWNER, "pack": "nope", "_csrf_token": token},
            headers={"Cookie": cookie, "HX-Request": "true"},
        )
    assert error.status == 422
    assert copy["message"] in error.text
    assert copy["next"] in error.text
    assert "invalid_pack" in error.text
    assert 'class="alert"' in error.text
    assert "htmx-indicator" in error.text
    assert "Start Stripe Checkout" in error.text
    assert "<html" not in error.text.lower()


@pytest.mark.issue(477)
async def test_top_up_form_post_wallet_disabled_without_js(example_app) -> None:
    from pages.wallet._errors import KNOWN

    copy = KNOWN["wallet_disabled"]
    async with TestClient(example_app) as client:
        cookie, token = await _form_session(client)
        response = await client.post(
            "/wallet/top-up",
            data={"owner_id": OWNER, "pack": "starter", "_csrf_token": token},
            headers={"Cookie": cookie},
        )
        assert response.status == 303
        location = response.header("Location")
        assert location
        assert "error=wallet_disabled" in location
        landed = await client.get(location, headers={"Cookie": cookie})
    assert landed.status == 200
    assert copy["message"] in landed.text
    assert copy["next"] in landed.text
