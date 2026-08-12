"""Tests for orrery/acceptance-bind — AcceptanceReceipt per ADR 0009 (#320)."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from dogfood import verify_receipt as verify_envelope_wire
from stars.acceptance_bind.contract import tool_schemas
from stars.acceptance_bind.service import acceptance_digest, bind, verify_receipt
from stars.acceptance_bind.skill import build_skill
from stars.builtins import builtin_registry
from tests.stars.helpers import (
    assert_manifest_publish_corpus,
    assert_payload_keys,
    assert_tool_schema_keys,
    load_star_manifest,
)

GOLDEN_ACCEPTANCE_ID = "leaf-320"
GOLDEN_CRITERIA = [
    {
        "id": "pytest-leaf",
        "statement": "issue marker green",
        "verify": {"kind": "pytest", "ref": "tests/stars/test_acceptance_bind.py"},
    },
    {
        "id": "ruff",
        "statement": "ruff check clean",
        "verify": {"kind": "command", "ref": "uv run ruff check .", "expect": "0"},
    },
]
GOLDEN_DIGEST = acceptance_digest(GOLDEN_ACCEPTANCE_ID, GOLDEN_CRITERIA)
FIXED_TIME = datetime(2026, 8, 12, 14, 30, 0, tzinfo=UTC)


@pytest.mark.issue(320)
def test_golden_digest_stability_and_criteria_order_independent() -> None:
    reversed_criteria = list(reversed(GOLDEN_CRITERIA))
    assert acceptance_digest(GOLDEN_ACCEPTANCE_ID, GOLDEN_CRITERIA) == GOLDEN_DIGEST
    assert acceptance_digest(GOLDEN_ACCEPTANCE_ID, reversed_criteria) == GOLDEN_DIGEST


@pytest.mark.issue(320)
def test_acceptance_id_nfc_normalization() -> None:
    nfd = "cafe\u0301-320"
    nfc = "caf\u00e9-320"
    assert acceptance_digest(nfd, GOLDEN_CRITERIA) == acceptance_digest(nfc, GOLDEN_CRITERIA)


@pytest.mark.issue(320)
def test_bind_happy_path_and_verify_receipt() -> None:
    result = bind(
        GOLDEN_ACCEPTANCE_ID,
        GOLDEN_CRITERIA,
        adr_url="https://github.com/lbliii/orrery/blob/main/docs/adr/0009-acceptance-receipt.md",
        issue_url="https://github.com/lbliii/orrery/issues/320",
        clock=lambda: FIXED_TIME,
    )
    assert_payload_keys(
        result,
        (
            "acceptance_id",
            "criteria",
            "acceptance_digest",
            "sealed_at",
            "adr_url",
            "issue_url",
        ),
    )
    assert result["acceptance_digest"] == GOLDEN_DIGEST
    assert result["acceptance_id"] == GOLDEN_ACCEPTANCE_ID
    assert result["sealed_at"] == FIXED_TIME.isoformat()
    assert len(result["criteria"]) == 2
    assert verify_receipt(result) == {"verified": True}


@pytest.mark.issue(320)
def test_bind_validation_errors_are_loud() -> None:
    assert bind("", GOLDEN_CRITERIA)["error"] == "acceptance_id_invalid"
    assert bind("x" * 129, GOLDEN_CRITERIA)["error"] == "acceptance_id_invalid"
    assert bind(GOLDEN_ACCEPTANCE_ID, [])["error"] == "criteria_empty"
    assert bind(GOLDEN_ACCEPTANCE_ID, None)["error"] == "criteria_invalid"  # type: ignore[arg-type]
    assert bind(GOLDEN_ACCEPTANCE_ID, GOLDEN_CRITERIA * 17)["error"] == "criteria_too_many"
    duplicate = [
        GOLDEN_CRITERIA[0],
        {**GOLDEN_CRITERIA[0], "statement": "different text"},
    ]
    assert bind(GOLDEN_ACCEPTANCE_ID, duplicate)["error"] == "duplicate_criterion_id"
    bad_kind = [
        {
            "id": "bad-kind",
            "statement": "x",
            "verify": {"kind": "playwright", "ref": "x"},
        }
    ]
    assert bind(GOLDEN_ACCEPTANCE_ID, bad_kind)["error"] == "verify_kind_invalid"
    assert bind(GOLDEN_ACCEPTANCE_ID, GOLDEN_CRITERIA, adr_url="http://insecure.example") == {
        "error": "url_not_https",
        "field": "adr_url",
        "url": "http://insecure.example",
    }


@pytest.mark.issue(320)
def test_verify_receipt_rejects_digest_tamper() -> None:
    receipt = bind(GOLDEN_ACCEPTANCE_ID, GOLDEN_CRITERIA, clock=lambda: FIXED_TIME)
    tampered = dict(receipt)
    tampered["acceptance_digest"] = "0" * 64
    result = verify_receipt(tampered)
    assert result["verified"] is False
    assert result["error"] == "digest_mismatch"
    assert result["expected"] == GOLDEN_DIGEST


@pytest.mark.issue(320)
def test_verify_ref_expect_omitted_from_canonical_when_absent() -> None:
    with_expect = [
        {
            "id": "cmd",
            "statement": "exit zero",
            "verify": {"kind": "command", "ref": "true", "expect": "0"},
        }
    ]
    without_expect = [
        {
            "id": "cmd",
            "statement": "exit zero",
            "verify": {"kind": "command", "ref": "true"},
        }
    ]
    assert acceptance_digest("a1", with_expect) != acceptance_digest("a1", without_expect)


@pytest.mark.issue(320)
class TestL0AcceptanceBind:
    def test_contract_tools_and_empty_egress(self) -> None:
        manifest = load_star_manifest("acceptance_bind")
        assert manifest["policy"]["allowed_egress"] == []
        assert_tool_schema_keys(tool_schemas(), {"bind"})
        assert_manifest_publish_corpus("acceptance_bind")

    def test_invalid_criterion_type_fails_loud(self) -> None:
        assert bind(GOLDEN_ACCEPTANCE_ID, ["not-an-object"])["error"] == "criterion_not_object"

    def test_criterion_id_must_be_slug(self) -> None:
        bad = [
            {
                "id": "Not_A_Slug",
                "statement": "x",
                "verify": {"kind": "pytest", "ref": "tests/x.py"},
            }
        ]
        assert bind(GOLDEN_ACCEPTANCE_ID, bad)["error"] == "criterion_id_invalid"


@pytest.mark.issue(320)
def test_envelope_signs_and_verifies_via_dogfood_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private = Ed25519PrivateKey.generate()
    monkeypatch.setenv("ORRERY_STAR_PRIVATE_KEY", private.private_bytes_raw().hex())
    monkeypatch.setenv("ORRERY_STAR_KEY_ID", "stars-2026-08")

    skill = build_skill()
    envelope = next(item for item in skill._pending if item.name == "bind").handler(
        acceptance_id=GOLDEN_ACCEPTANCE_ID,
        criteria=GOLDEN_CRITERIA,
    )
    wire = envelope.to_wire()
    assert verify_envelope_wire(wire, skill=skill) is True

    payload = wire["payload"]
    assert_payload_keys(
        payload,
        ("acceptance_id", "criteria", "acceptance_digest", "sealed_at"),
    )
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


@pytest.mark.issue(320)
def test_package_contract_and_registry() -> None:
    assert {item.name for item in build_skill()._pending} == {"bind"}
    definition = next(
        item for item in builtin_registry() if item.name == "orrery/acceptance-bind"
    )
    assert definition.direct_mcp_path == "/stars/acceptance-bind/mcp"
