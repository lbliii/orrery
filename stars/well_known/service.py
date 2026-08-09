"""Bounded local projection of Orrery's named discovery documents."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from discovery import configured_public_origin, llms_txt, server_card

from .contract import DEFAULT_DOCUMENT, DOCUMENTS, MAX_BYTES, MAX_SLICE_CHARS


class PublicationProvider(Protocol):
    def __call__(self, document: str, canonical_url: str) -> bytes: ...


def _origin() -> str:
    return configured_public_origin() or "https://orrery.lol"


def _local_publication(document: str, canonical_url: str) -> bytes:
    """Project the same canonical generators served by the public app, without HTTP."""
    del canonical_url
    origin = _origin()
    if document == "orrery-llms":
        return llms_txt(origin).encode("utf-8")
    if document == "orrery-mcp-server-card":
        return json.dumps(server_card(origin), sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    raise ValueError("document_not_allowed")


def read(
    document: str = DEFAULT_DOCUMENT,
    *,
    provider: PublicationProvider = _local_publication,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    """Read only named documents from Orrery's local authoritative publication."""
    configured = DOCUMENTS.get(document)
    observed_at = (clock or (lambda: datetime.now(UTC)))().isoformat()
    if configured is None:
        return {"error": "document_not_allowed", "document": document, "live_at_call": True}
    url, kind = configured
    try:
        body = provider(document, url)
    except (OSError, ValueError) as error:
        return {
            "error": "publication_unavailable",
            "document": document,
            "detail": str(error),
            "live_at_call": True,
        }
    if len(body) > MAX_BYTES:
        return {"error": "publication_too_large", "document": document, "live_at_call": True}
    text = body.decode("utf-8", errors="replace")
    result: dict[str, object] = {
        "document": document,
        "canonical_url": url,
        "status": 200,
        "content_digest": f"sha256:{hashlib.sha256(body).hexdigest()}",
        "byte_length": len(body),
        "text_slice": text[:MAX_SLICE_CHARS],
        "slice_truncated": len(text) > MAX_SLICE_CHARS,
        "observed_at": observed_at,
        "live_at_call": True,
        "source": {"publisher": "Orrery", "document_type": kind, "provider": "local-authoritative"},
    }
    if kind == "mcp-card":
        try:
            card = json.loads(text)
            info = card.get("serverInfo", {}) if isinstance(card, dict) else {}
            transport = card.get("transport", {}) if isinstance(card, dict) else {}
            result["mcp_card"] = {
                "name": info.get("name"),
                "version": info.get("version"),
                "endpoint": transport.get("endpoint"),
            }
        except TypeError, json.JSONDecodeError:
            result["mcp_card"] = None
    return result
