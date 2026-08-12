"""Dogfood AcceptanceReceipt cite on constellation composite receipts (#321)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from chirp.skill import verify_envelope
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from catalog.constellation_run import reset_run_store, run_constellation, status_for_run
from dogfood import envelope_from_wire
from stars.acceptance_bind.service import bind, verify_receipt
from stars.stale_proof.composite_receipt import (
    normalize_acceptance_cites,
    with_acceptance_cites,
)

GOLDEN_ACCEPTANCE_ID = "dogfood-321"
GOLDEN_CRITERIA = [
    {
        "id": "acceptance-cites-test",
        "statement": "composite receipt lists acceptance_digest when stage requires it",
        "verify": {
            "kind": "pytest",
            "ref": "tests/stars/test_acceptance_cites_dogfood.py",
        },
    },
]
FIXED_TIME = datetime(2026, 8, 12, 14, 30, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _isolated_run_store() -> None:
    reset_run_store()


@pytest.mark.issue(321)
def test_composite_receipt_includes_acceptance_digest_cite_when_provided() -> None:
    bound = bind(
        GOLDEN_ACCEPTANCE_ID,
        GOLDEN_CRITERIA,
        clock=lambda: FIXED_TIME,
    )
    assert verify_receipt(bound)["verified"] is True
    digest = str(bound["acceptance_digest"])

    key = Ed25519PrivateKey.generate()
    result = run_constellation(
        {"pages": ["README.md"], "links": [], "examples": []},
        constellation="orrery/stale-proof",
        skill_name="launch-gate",
        skill_version="2.0.0",
        key_id="test-321",
        private_key=key,
        acceptance_cites=[digest],
    )

    serialized = json.dumps(result)
    assert digest in serialized
    assert result["acceptance_cites"] == [digest]
    assert "cites" not in result
    assert result["constellation"] == "orrery/stale-proof"
    assert result["status"] == "completed"

    status = status_for_run(result["run_id"])
    assert status["acceptance_cites"] == [digest]

    for step in result["chain"]:
        envelope = envelope_from_wire(step["envelope"])
        assert verify_envelope(envelope, key.public_key()) is True


@pytest.mark.issue(321)
def test_normalize_acceptance_cites_rejects_invalid_digest() -> None:
    with pytest.raises(ValueError, match="invalid acceptance_digest"):
        normalize_acceptance_cites(["not-a-digest"])

    digest = "a" * 64
    assert with_acceptance_cites({"run_id": "x"}, [digest])["acceptance_cites"] == [digest]
