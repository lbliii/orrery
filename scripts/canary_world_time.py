#!/usr/bin/env python3
"""Non-blocking public world-time + public-key signature canary."""
from __future__ import annotations

import argparse
import ast
import base64
import json
import sys
import urllib.request
from datetime import UTC, datetime
from typing import Any

from chirp.skill import Envelope, verify_envelope

REQUIRED = frozenset(
    {"payload", "skill", "version", "tool", "nonce", "input_digest", "signature", "key_id", "alg"}
)


def parse_envelope(text: str) -> dict[str, object]:
    """Parse the Chirp text representation without executing its contents."""
    node = ast.parse(text, mode="eval").body
    if (
        not isinstance(node, ast.Call)
        or not isinstance(node.func, ast.Name)
        or node.func.id != "Envelope"
        or node.args
        or any(keyword.arg is None for keyword in node.keywords)
    ):
        raise ValueError("expected Envelope keyword literal")
    result = {keyword.arg: ast.literal_eval(keyword.value) for keyword in node.keywords}
    if set(result) != REQUIRED:
        raise ValueError("unexpected Envelope fields")
    return result


def request(url: str, body: bytes | None = None) -> bytes:
    headers = {"Content-Type": "application/json"} if body else {}
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as response:
        return response.read()


def verify(envelope: dict[str, object], keys: dict[str, object]) -> None:
    """Verify an Envelope with the public key published for this Star only."""
    kid = str(envelope["key_id"])
    try:
        jwk = next(
            item
            for item in keys["keys"]
            if item["kid"] == kid and item.get("star") == "orrery/world-time"
        )
    except (KeyError, StopIteration) as exc:
        raise ValueError("world-time public key not found") from exc
    raw_x = str(jwk["x"])
    raw = base64.urlsafe_b64decode(raw_x + "=" * (-len(raw_x) % 4))
    if not verify_envelope(Envelope(**envelope), raw):
        raise ValueError("invalid Envelope signature")


def validate_payload(envelope: dict[str, object], *, now: datetime | None = None) -> None:
    """Assert the receipt is a fresh, live UTC response (provider timestamps are UTC)."""
    value = envelope["payload"]
    if not isinstance(value, dict):
        raise ValueError("world-time payload must be an object")
    if (
        envelope["skill"] != "world-time"
        or envelope["tool"] != "fetch"
        or value.get("timezone") != "UTC"
        or value.get("live_at_call") is not True
    ):
        raise ValueError("unexpected world-time receipt")
    received = value.get("datetime")
    if not isinstance(received, str):
        raise ValueError("world-time receipt has no datetime")
    when = datetime.fromisoformat(received.replace("Z", "+00:00"))
    # The provider's documented UTC ISO value is offset-naive; give that value
    # its declared UTC meaning before comparing with our offset-aware clock.
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    current = now or datetime.now(UTC)
    if abs((current - when).total_seconds()) > 900:
        raise ValueError("UTC response outside 15 minute skew")


def run(origin: str) -> None:
    payload: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "fetch", "arguments": {}},
    }
    wire = json.loads(request(origin + "/stars/world-time/mcp", json.dumps(payload).encode()))
    text = wire["result"]["content"][0]["text"]
    envelope = parse_envelope(text)
    verify(envelope, json.loads(request(origin + "/.well-known/orrery/keys.json")))
    validate_payload(envelope)

if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", default="https://orrery.lol")
    try:
        run(parser.parse_args().origin.rstrip("/"))
    except Exception as error:
        print(f"world-time canary failed: {error}", file=sys.stderr)
        raise
