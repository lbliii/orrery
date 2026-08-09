"""Signed MCP adapter for bounded HTTP metadata observations."""

from __future__ import annotations

import os
from typing import Any

from chirp.skill import Skill
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .contract import DEFAULT_TARGET, STAR_VERSION
from .service import head as observe_head


def _private_key(private_key: Any | None) -> Ed25519PrivateKey:
    if private_key is not None:
        return private_key
    raw = os.environ.get("ORRERY_HTTP_HEAD_PRIVATE_KEY", "").strip()
    return (
        Ed25519PrivateKey.from_private_bytes(bytes.fromhex(raw))
        if raw
        else Ed25519PrivateKey.generate()
    )


def build_skill(*, private_key: Any | None = None) -> Skill:
    private = _private_key(private_key)
    skill = Skill(
        "http-head",
        version=STAR_VERSION,
        private_key=private,
        key_id=os.environ.get("ORRERY_HTTP_HEAD_KEY_ID", "orrery-http-head-1"),
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool("head", description="Fetch fresh metadata for an allowlisted official HTTP target")
    def head(target: str = DEFAULT_TARGET) -> dict[str, object]:
        return observe_head(target)

    return skill
