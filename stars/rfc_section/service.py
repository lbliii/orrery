"""Bounded canonical RFC Editor text retrieval and section extraction."""

from __future__ import annotations

import hashlib
import re
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import urlsplit

from .contract import (
    ALLOWED_SECTIONS,
    DEFAULT_RFC,
    DEFAULT_SECTION,
    MAX_BYTES,
    MAX_SLICE_CHARS,
    RFC_SOURCES,
)

TIMEOUT_SECONDS = 8


class Fetch(Protocol):
    def __call__(
        self, url: str, *, timeout: float, max_bytes: int
    ) -> tuple[str, int, Mapping[str, str], bytes]: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def _network_fetch(
    url: str, *, timeout: float, max_bytes: int
) -> tuple[str, int, Mapping[str, str], bytes]:
    request = urllib.request.Request(url, headers={"User-Agent": "orrery-rfc-section/0.1"})
    with urllib.request.build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
        return (
            response.geturl(),
            int(response.status),
            dict(response.headers.items()),
            response.read(max_bytes + 1),
        )


def get(
    rfc: str = DEFAULT_RFC,
    section: str = DEFAULT_SECTION,
    *,
    fetch: Fetch = _network_fetch,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    url = RFC_SOURCES.get(rfc)
    observed = (clock or (lambda: datetime.now(UTC)))().isoformat()
    if url is None or section not in ALLOWED_SECTIONS.get(rfc, frozenset()):
        return {
            "error": "rfc_or_section_not_allowed",
            "rfc": rfc,
            "section": section,
            "live_at_call": True,
        }
    try:
        final_url, status, _headers, body = fetch(url, timeout=TIMEOUT_SECONDS, max_bytes=MAX_BYTES)
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        OSError,
        ValueError,
    ) as error:
        return {
            "error": "upstream_unreachable",
            "rfc": rfc,
            "section": section,
            "detail": str(error),
            "live_at_call": True,
        }
    final = urlsplit(final_url)
    if final.scheme != "https" or final.hostname != "www.rfc-editor.org":
        return {
            "error": "redirect_not_allowed",
            "rfc": rfc,
            "section": section,
            "live_at_call": True,
        }
    if len(body) > MAX_BYTES:
        return {"error": "upstream_too_large", "rfc": rfc, "section": section, "live_at_call": True}
    text = body.decode("utf-8", errors="replace")
    slice_text = _section(text, section)
    if slice_text is None:
        return {"error": "section_not_found", "rfc": rfc, "section": section, "live_at_call": True}
    return {
        "rfc": rfc,
        "section": section,
        "canonical_url": final_url,
        "status": status,
        "source_digest": f"sha256:{hashlib.sha256(body).hexdigest()}",
        "slice_digest": f"sha256:{hashlib.sha256(slice_text.encode()).hexdigest()}",
        "text_slice": slice_text[:MAX_SLICE_CHARS],
        "slice_truncated": len(slice_text) > MAX_SLICE_CHARS,
        "observed_at": observed,
        "source": {"publisher": "RFC Editor", "format": "text/plain"},
        "live_at_call": True,
    }


def _section(text: str, section: str) -> str | None:
    start = re.compile(rf"^\s*{re.escape(section)}\.\s+.+$", re.MULTILINE).search(text)
    if start is None:
        return None
    remainder = text[start.start() :]
    headings = re.compile(r"^\s*\d+(?:\.\d+)*\.\s+.+$", re.MULTILINE)
    next_heading = next(
        (match for match in headings.finditer(remainder) if match.start() > 0), None
    )
    return remainder[: next_heading.start()].strip() if next_heading else remainder.strip()
