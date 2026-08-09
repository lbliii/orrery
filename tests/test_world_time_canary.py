"""Tests for the public world-time receipt verifier."""

from __future__ import annotations

import base64
from datetime import UTC, datetime

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from chirp.skill import Skill

from scripts.canary_world_time import parse_envelope, validate_payload, verify


def signed_envelope() -> tuple[dict[str, object], dict[str, object]]:
    private = Ed25519PrivateKey.generate()
    skill = Skill("world-time", version="0.1.0", private_key=private, key_id="test-world-time")

    @skill.tool("fetch")
    def fetch() -> dict[str, object]:
        return {"timezone": "UTC", "datetime": "2026-08-09T12:00:00", "live_at_call": True}

    envelope = skill._pending[0].handler().to_wire()
    public = private.public_key().public_bytes_raw()
    keys = {
        "keys": [
            {
                "kid": "test-world-time",
                "star": "orrery/world-time",
                "x": base64.urlsafe_b64encode(public).decode().rstrip("="),
            }
        ]
    }
    return envelope, keys


def test_valid_signed_world_time_receipt_is_verified() -> None:
    envelope, keys = signed_envelope()

    verify(envelope, keys)
    validate_payload(envelope, now=datetime(2026, 8, 9, 12, 1, tzinfo=UTC))


@pytest.mark.parametrize(
    "text",
    [
        "Envelope(payload={'x': 1})",
        "Envelope(**{'payload': {}})",
        "not_an_envelope()",
    ],
)
def test_parser_rejects_incomplete_or_executable_text(text: str) -> None:
    with pytest.raises(ValueError):
        parse_envelope(text)


def test_verify_rejects_tampered_receipt_and_wrong_star_key() -> None:
    envelope, keys = signed_envelope()
    tampered = {**envelope, "payload": {**envelope["payload"], "timezone": "EST"}}
    with pytest.raises(ValueError, match="invalid Envelope signature"):
        verify(tampered, keys)

    keys["keys"][0]["star"] = "orrery/another-star"
    with pytest.raises(ValueError, match="public key not found"):
        verify(envelope, keys)


def test_validate_payload_interprets_naive_provider_time_as_utc() -> None:
    envelope, _ = signed_envelope()
    validate_payload(envelope, now=datetime(2026, 8, 9, 12, 1, tzinfo=UTC))

    stale = {**envelope, "payload": {**envelope["payload"], "datetime": "2026-08-09T11:00:00"}}
    with pytest.raises(ValueError, match="outside"):
        validate_payload(stale, now=datetime(2026, 8, 9, 12, 1, tzinfo=UTC))
