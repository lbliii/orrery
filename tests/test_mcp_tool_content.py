"""ADR 0010 / 0011 structured MCP bodies (#430)."""

from __future__ import annotations

import pytest
from chirp.skill import Skill, sign_envelope
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from catalog.mcp_tool_content import (
    structured_tool_body,
    wrap_structured_mcp_handler,
)


def _signed_envelope(payload: dict[str, object]):
    key = Ed25519PrivateKey.generate()
    return sign_envelope(
        payload=payload,
        skill="html-to-pdf",
        version="0.1.0",
        tool="result",
        input_digest="sha256:" + "b" * 64,
        private_key=key,
        key_id="test-430",
    )


@pytest.mark.issue(430)
def test_unsigned_not_found_becomes_mcp_error() -> None:
    body = structured_tool_body(
        {"error": "not_found", "name": "orrery/no-such-skill", "status": "not_found"},
        skill="resolve",
        tool="resolve_name",
    )
    assert body["status"] == "error"
    assert body["error"]["code"] == "not_found"
    assert "envelope_wire" not in body
    assert "Skill not found" in body["error"]["message"]


@pytest.mark.issue(430)
def test_wrap_unsigned_resolve_name_miss_is_mcp_error() -> None:
    def resolve_name(name: str) -> dict[str, object]:
        return {"error": "not_found", "name": name, "status": "not_found"}

    wrapped = wrap_structured_mcp_handler(
        resolve_name, skill="resolve", tool="resolve_name"
    )
    body = wrapped(name="orrery/no-such-skill")
    assert body["status"] == "error"
    assert body["error"]["code"] == "not_found"
    assert "envelope_wire" not in body


@pytest.mark.issue(430)
def test_signed_envelope_with_payload_error_stays_ok() -> None:
    envelope = _signed_envelope({"error": "run_not_found", "run_id": "missing"})
    body = structured_tool_body(envelope, skill="html-to-pdf", tool="result")
    assert body["status"] == "ok"
    assert "envelope_wire" in body
    assert body["payload"]["error"] == "run_not_found"


@pytest.mark.issue(430)
def test_signed_wire_with_payload_error_stays_ok() -> None:
    wire = _signed_envelope({"error": "run_not_found", "run_id": "missing"}).to_wire()
    body = structured_tool_body(wire, skill="html-to-pdf", tool="result")
    assert body["status"] == "ok"
    assert body["envelope_wire"] == wire
    assert body["payload"]["error"] == "run_not_found"


@pytest.mark.issue(430)
def test_unsigned_error_prefers_detail_message() -> None:
    body = structured_tool_body(
        {"error": "unknown_tool", "detail": "No convert tool"},
        skill="gaze",
        tool="gaze_describe",
    )
    assert body["status"] == "error"
    assert body["error"]["code"] == "unknown_tool"
    assert body["error"]["message"] == "No convert tool"
    assert "envelope_wire" not in body


@pytest.mark.issue(430)
def test_skill_tool_discovery_miss_skips_chirp_seal() -> None:
    key = Ed25519PrivateKey.generate()
    skill = Skill(
        "resolve",
        version="1.0.0",
        private_key=key,
        key_id="test-430",
        public_key=key.public_key().public_bytes_raw(),
    )

    @skill.tool("resolve_name", description="Resolve a name")
    def resolve_name(name: str) -> dict[str, object]:
        return {"error": "not_found", "name": name, "status": "not_found"}

    wrapped = wrap_structured_mcp_handler(
        skill._pending[0].handler, skill="resolve", tool="resolve_name"
    )
    body = wrapped(name="orrery/no-such-skill")
    assert body["status"] == "error"
    assert body["error"]["code"] == "not_found"
    assert "envelope_wire" not in body


@pytest.mark.issue(430)
def test_skill_tool_signed_negative_stays_ok() -> None:
    key = Ed25519PrivateKey.generate()
    skill = Skill(
        "html-to-pdf",
        version="0.1.0",
        private_key=key,
        key_id="test-430",
        public_key=key.public_key().public_bytes_raw(),
    )

    @skill.tool("result", description="Poll a run")
    def result(run_id: str) -> dict[str, object]:
        return {"error": "run_not_found", "run_id": run_id}

    wrapped = wrap_structured_mcp_handler(
        skill._pending[0].handler, skill="html-to-pdf", tool="result"
    )
    body = wrapped(run_id="missing")
    assert body["status"] == "ok"
    assert body["payload"]["error"] == "run_not_found"
    assert "envelope_wire" in body
