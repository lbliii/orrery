"""Bounded retrieval of a tiny fixed set of official discovery documents."""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import urlsplit

from .contract import DEFAULT_DOCUMENT, DOCUMENTS, MAX_BYTES, MAX_SLICE_CHARS

TIMEOUT_SECONDS = 8
ALLOWED_HOSTS = frozenset(urlsplit(url).hostname for url, _ in DOCUMENTS.values())


class Transport(Protocol):
    def __call__(
        self, url: str, *, timeout: float, max_bytes: int
    ) -> tuple[str, int, Mapping[str, str], bytes]: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def _network_fetch(
    url: str, *, timeout: float, max_bytes: int
) -> tuple[str, int, Mapping[str, str], bytes]:
    request = urllib.request.Request(url, headers={"User-Agent": "orrery-well-known/0.1"})
    with urllib.request.build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
        body = response.read(max_bytes + 1)
        return response.geturl(), int(response.status), dict(response.headers.items()), body


def read(
    document: str = DEFAULT_DOCUMENT,
    *,
    transport: Transport = _network_fetch,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    configured = DOCUMENTS.get(document)
    observed_at = (clock or (lambda: datetime.now(UTC)))().isoformat()
    if configured is None:
        return {"error": "document_not_allowed", "document": document, "live_at_call": True}
    url, kind = configured
    try:
        final_url, status, _headers, body = transport(
            url, timeout=TIMEOUT_SECONDS, max_bytes=MAX_BYTES
        )
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        OSError,
        ValueError,
    ) as error:
        return {
            "error": "upstream_unreachable",
            "document": document,
            "detail": str(error),
            "live_at_call": True,
        }
    final = urlsplit(final_url)
    if final.scheme != "https" or final.hostname not in ALLOWED_HOSTS:
        return {"error": "redirect_not_allowed", "document": document, "live_at_call": True}
    if len(body) > MAX_BYTES:
        return {"error": "upstream_too_large", "document": document, "live_at_call": True}
    text = body.decode("utf-8", errors="replace")
    result: dict[str, object] = {
        "document": document,
        "canonical_url": final_url,
        "status": status,
        "content_digest": f"sha256:{hashlib.sha256(body).hexdigest()}",
        "byte_length": len(body),
        "text_slice": text[:MAX_SLICE_CHARS],
        "slice_truncated": len(text) > MAX_SLICE_CHARS,
        "observed_at": observed_at,
        "live_at_call": True,
        "source": {"publisher": "Orrery", "document_type": kind, "requested_url": url},
    }
    if kind == "mcp-card":
        try:
            card = json.loads(text)
            info = card.get("serverInfo", {}) if isinstance(card, dict) else {}
            transport_info = card.get("transport", {}) if isinstance(card, dict) else {}
            result["mcp_card"] = {
                "name": info.get("name"),
                "version": info.get("version"),
                "endpoint": transport_info.get("endpoint"),
            }
        except TypeError, json.JSONDecodeError:
            result["mcp_card"] = None
    return result
