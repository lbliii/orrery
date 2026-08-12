"""Tests for orrery/decision-bind — DecisionReceipt per ADR 0006 (#244)."""

from __future__ import annotations

import base64
import hashlib
import json
import unicodedata
from datetime import UTC, datetime

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from dogfood import verify_receipt as verify_envelope_wire
from stars._core.attribution import PAYLOAD_VIA
from stars.builtins import builtin_registry
from stars.decision_bind.contract import MAX_STATEMENT_BYTES, tool_schemas
from stars.decision_bind.service import bind, decision_digest, verify_receipt
from stars.decision_bind.skill import build_skill
from tests.stars.helpers import (
    assert_manifest_publish_corpus,
    assert_payload_keys,
    assert_tool_schema_keys,
    load_star_manifest,
)

GOLDEN_STATEMENT = (
    "pause for typed decision on unsupported MyST directive; do not invent MDX."
)
GOLDEN_DIGEST = hashlib.sha256(
    unicodedata.normalize("NFC", GOLDEN_STATEMENT).encode("utf-8")
).hexdigest()
FIXED_TIME = datetime(2026, 8, 10, 12, 34, 56, tzinfo=UTC)


@pytest.mark.issue(244)
def test_golden_digest_stability_and_nfc_normalization() -> None:
    assert decision_digest(GOLDEN_STATEMENT) == GOLDEN_DIGEST
    nfd = "cafe\u0301"  # e + combining acute — same digest after NFC as precomposed café
    assert decision_digest(nfd) == decision_digest("caf\u00e9")


@pytest.mark.issue(244)
def test_bind_happy_path_and_verify_receipt() -> None:
    result = bind(
        "planner-freeze-1",
        GOLDEN_STATEMENT,
        adr_url="https://github.com/lbliii/orrery/blob/main/docs/adr/0006-decision-receipt.md",
        issue_url="https://github.com/lbliii/orrery/issues/244",
        clock=lambda: FIXED_TIME,
    )
    assert_payload_keys(
        result,
        ("decision_id", "statement", "decision_digest", "decided_at", "adr_url", "issue_url"),
    )
    assert result["decision_digest"] == GOLDEN_DIGEST
    assert result["statement"] == GOLDEN_STATEMENT
    assert result["decided_at"] == FIXED_TIME.isoformat()
    assert verify_receipt(result) == {"verified": True}


@pytest.mark.issue(244)
def test_bind_validation_errors_are_loud() -> None:
    assert bind("", GOLDEN_STATEMENT)["error"] == "decision_id_invalid"
    assert bind("x" * 129, GOLDEN_STATEMENT)["error"] == "decision_id_invalid"
    assert bind("id", "")["error"] == "statement_empty"
    assert bind("id", "x" * (MAX_STATEMENT_BYTES + 1))["error"] == "statement_too_large"
    assert bind("id", GOLDEN_STATEMENT, adr_url="http://insecure.example") == {
        "error": "url_not_https",
        "field": "adr_url",
        "url": "http://insecure.example",
    }


@pytest.mark.issue(244)
def test_verify_receipt_rejects_digest_tamper() -> None:
    receipt = bind("id", GOLDEN_STATEMENT, clock=lambda: FIXED_TIME)
    tampered = dict(receipt)
    tampered["decision_digest"] = "0" * 64
    result = verify_receipt(tampered)
    assert result["verified"] is False
    assert result["error"] == "digest_mismatch"
    assert result["expected"] == GOLDEN_DIGEST


@pytest.mark.issue(244)
class TestL0DecisionBind:
    def test_contract_tools_and_empty_egress(self) -> None:
        manifest = load_star_manifest("decision_bind")
        assert manifest["policy"]["allowed_egress"] == []
        assert_tool_schema_keys(tool_schemas(), {"bind"})
        assert_manifest_publish_corpus("decision_bind")

    def test_invalid_statement_type_fails_loud(self) -> None:
        assert bind("id", None)["error"] == "statement_invalid"  # type: ignore[arg-type]


@pytest.mark.issue(244)
def test_envelope_signs_and_verifies_via_dogfood_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private = Ed25519PrivateKey.generate()
    monkeypatch.setenv("ORRERY_STAR_PRIVATE_KEY", private.private_bytes_raw().hex())
    monkeypatch.setenv("ORRERY_STAR_KEY_ID", "stars-2026-08")

    skill = build_skill()
    envelope = next(item for item in skill._pending if item.name == "bind").handler(
        decision_id="planner-freeze-1",
        statement=GOLDEN_STATEMENT,
    )
    wire = envelope.to_wire()
    assert verify_envelope_wire(wire, skill=skill) is True

    payload = wire["payload"]
    assert_payload_keys(
        payload,
        ("decision_id", "statement", "decision_digest", "decided_at", "via"),
    )
    assert payload["via"] == PAYLOAD_VIA
    assert verify_receipt(payload) == {"verified": True}

    fields = {
        name: wire[name]
        for name in (
            "payload",
            "skill",
            "version",
            "tool",
            "nonce",
            "input_digest",
            "key_id",
            "alg",
        )
    }
    message = json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    raw = private.public_key().public_bytes_raw()
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    Ed25519PublicKey.from_public_bytes(raw).verify(
        base64.b64decode(str(wire["signature"])), message
    )


@pytest.mark.issue(318)
def test_envelope_via_does_not_change_decision_digest() -> None:
    receipt = bind("id", GOLDEN_STATEMENT, clock=lambda: FIXED_TIME)
    assert receipt["decision_digest"] == GOLDEN_DIGEST
    assert "via" not in receipt


@pytest.mark.issue(318)
def test_envelope_error_payload_omits_via() -> None:
    skill = build_skill()
    envelope = next(item for item in skill._pending if item.name == "bind").handler(
        decision_id="",
        statement=GOLDEN_STATEMENT,
    )
    payload = envelope.to_wire()["payload"]
    assert payload["error"] == "decision_id_invalid"
    assert "via" not in payload


@pytest.mark.issue(244)
def test_package_contract_and_registry() -> None:
    assert {item.name for item in build_skill()._pending} == {"bind"}
    definition = next(
        item for item in builtin_registry() if item.name == "orrery/decision-bind"
    )
    assert definition.direct_mcp_path == "/stars/decision-bind/mcp"
