"""Chirp/MCP adapter for the World Time Star contract."""

from __future__ import annotations

import os
from typing import Any

from chirp.skill import Skill
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .contract import STAR_VERSION
from .service import answer as answer_now
from .service import fetch as fetch_now
from .service import get as get_now


def _private_key(private_key: Any | None) -> Ed25519PrivateKey:
    if private_key is not None:
        return private_key
    raw = os.environ.get("ORRERY_WORLD_TIME_PRIVATE_KEY", "").strip()
    if raw:
        return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(raw))
    return Ed25519PrivateKey.generate()


def build_skill(*, private_key: Any | None = None) -> Skill:
    """Build the direct-endpoint World Time skill with canonical tool names."""
    private = _private_key(private_key)
    skill = Skill(
        "world-time",
        version=STAR_VERSION,
        private_key=private,
        key_id=os.environ.get("ORRERY_WORLD_TIME_KEY_ID", "orrery-world-time-1"),
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "fetch", description="Fetch live UTC from the public clock API (signed at call time)"
    )
    def fetch() -> dict[str, object]:
        return fetch_now()

    @skill.tool("get", description="Get the live UTC reading (same live source as fetch)")
    def get() -> dict[str, object]:
        return get_now()

    @skill.tool("answer", description="Answer with the live UTC datetime sealed in an Envelope")
    def answer() -> dict[str, object]:
        return answer_now()

    return skill
