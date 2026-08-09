"""Chirp/MCP adapter for the html-to-pdf Star contract."""

from __future__ import annotations

import base64
import os
from typing import Any

from chirp.skill import Skill
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .artifacts import artifact_store
from .contract import STAR_VERSION
from .service import convert as convert_html
from .service import health as health_check


def _private_key(private_key: Any | None) -> Ed25519PrivateKey:
    if private_key is not None:
        return private_key
    raw = os.environ.get("ORRERY_PDF_PRIVATE_KEY", "").strip()
    if raw:
        return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(raw))
    return Ed25519PrivateKey.generate()


def build_skill(*, private_key: Any | None = None) -> Skill:
    """Build the direct-endpoint html-to-pdf skill with canonical tool names."""
    private = _private_key(private_key)
    skill = Skill(
        "html-to-pdf",
        version=STAR_VERSION,
        private_key=private,
        key_id=os.environ.get("ORRERY_PDF_KEY_ID", "orrery-pdf-1"),
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "convert",
        description="Render simple HTML to a short-lived PDF artifact with verifiable metadata",
    )
    def convert(html: str) -> dict[str, object]:
        result = convert_html(html)
        encoded = str(result.pop("artifact_base64"))
        artifact = artifact_store.put(base64.b64decode(encoded, validate=True))
        result["artifact_url"] = f"/artifacts/{artifact.artifact_id}"
        result["sha256"] = artifact.sha256
        return result

    @skill.tool("health", description="html-to-pdf readiness probe")
    def health() -> dict[str, str]:
        return health_check()

    return skill
