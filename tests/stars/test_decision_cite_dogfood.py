"""Dogfood DecisionReceipt cite on constellation composite receipts (#245)."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import UTC, datetime

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from catalog.constellation_run import run_constellation, status_for_run
from dogfood import build_launch_gate_skill
from stars.decision_bind.service import bind, decision_digest, verify_receipt
from stars.stale_proof.composite_receipt import normalize_cites, with_cites

GOLDEN_STATEMENT = (
    "pause for typed decision on unsupported MyST directive; do not invent MDX."
)
GOLDEN_DIGEST = hashlib.sha256(
    unicodedata.normalize("NFC", GOLDEN_STATEMENT).encode("utf-8")
).hexdigest()
FIXED_TIME = datetime(2026, 8, 10, 12, 34, 56, tzinfo=UTC)


@pytest.mark.issue(245)
def test_composite_receipt_includes_decision_digest_cite_when_provided() -> None:
    bound = bind("dogfood-245", GOLDEN_STATEMENT, clock=lambda: FIXED_TIME)
    assert verify_receipt(bound)["verified"] is True
    digest = str(bound["decision_digest"])
    assert digest == GOLDEN_DIGEST

    key = Ed25519PrivateKey.generate()
    result = run_constellation(
        {"pages": ["README.md"], "links": [], "examples": []},
        constellation="orrery/stale-proof",
        skill_name="launch-gate",
        skill_version="2.0.0",
        key_id="test-245",
        private_key=key,
        cites=[digest],
    )

    serialized = json.dumps(result)
    assert digest in serialized
    assert result["cites"] == [digest]
    assert result["constellation"] == "orrery/stale-proof"
    assert result["status"] == "completed"

    status = status_for_run(result["run_id"])
    assert status["cites"] == [digest]


@pytest.mark.issue(245)
def test_launch_gate_run_tool_binds_decision_and_cites_digest() -> None:
    skill = build_launch_gate_skill()
    run_handler = next(item for item in skill._pending if item.name == "run").handler
    envelope = run_handler(
        pages=["README.md"],
        constellation="orrery/stale-proof",
        decision_id="planner-freeze-245",
        decision_statement=GOLDEN_STATEMENT,
    )
    payload = envelope.payload
    assert payload["cites"] == [GOLDEN_DIGEST]
    assert decision_digest(GOLDEN_STATEMENT) in json.dumps(payload)


@pytest.mark.issue(245)
def test_normalize_cites_rejects_invalid_digest() -> None:
    with pytest.raises(ValueError, match="invalid decision_digest"):
        normalize_cites(["not-a-digest"])

    assert with_cites({"run_id": "x"}, [GOLDEN_DIGEST])["cites"] == [GOLDEN_DIGEST]
