"""Bounded canonical PEP HTML fetch and exact heading-section extraction."""

from __future__ import annotations

import hashlib
import re
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any, Protocol
from urllib.parse import urlsplit

from .contract import (
    ALLOWED_SECTIONS,
    DEFAULT_PEP,
    DEFAULT_SECTION,
    MAX_BYTES,
    MAX_SLICE_CHARS,
    PEP_SOURCES,
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
    request = urllib.request.Request(url, headers={"User-Agent": "orrery-pep-section/0.1"})
    with urllib.request.build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
        return (
            response.geturl(),
            int(response.status),
            dict(response.headers.items()),
            response.read(max_bytes + 1),
        )


class _Sections(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._heading: list[str] | None = None
        self._level = 0
        self._current: tuple[str, list[str]] | None = None
        self.sections: list[tuple[str, str]] = []
        self._hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in {"script", "style", "nav"}:
            self._hidden += 1
        if self._hidden:
            return
        if tag in {"h1", "h2", "h3"}:
            if self._current:
                self.sections.append((self._current[0], "\n".join(self._current[1])))
            self._heading, self._level = [], int(tag[1])

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "nav"}:
            self._hidden = max(0, self._hidden - 1)
            return
        if self._hidden:
            return
        if self._heading is not None and tag == f"h{self._level}":
            self._current = ("".join(self._heading).strip(), [])
            self._heading = None

    def handle_data(self, data: str) -> None:
        if self._hidden:
            return
        if self._heading is not None:
            self._heading.append(data)
        elif self._current is not None and data.strip():
            self._current[1].append(" ".join(data.split()))

    def finish(self) -> None:
        if self._current:
            self.sections.append((self._current[0], "\n".join(self._current[1])))


def get(
    pep: str = DEFAULT_PEP,
    section: str = DEFAULT_SECTION,
    *,
    fetch: Fetch = _network_fetch,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    url = PEP_SOURCES.get(pep)
    observed = (clock or (lambda: datetime.now(UTC)))().isoformat()
    if url is None or section not in ALLOWED_SECTIONS.get(pep, frozenset()):
        return {
            "error": "pep_or_section_not_allowed",
            "pep": pep,
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
            "pep": pep,
            "section": section,
            "detail": str(error),
            "live_at_call": True,
        }
    final = urlsplit(final_url)
    if final.scheme != "https" or final.hostname != "peps.python.org":
        return {
            "error": "redirect_not_allowed",
            "pep": pep,
            "section": section,
            "live_at_call": True,
        }
    if len(body) > MAX_BYTES:
        return {"error": "upstream_too_large", "pep": pep, "section": section, "live_at_call": True}
    parser = _Sections()
    parser.feed(body.decode("utf-8", errors="replace"))
    parser.finish()
    candidates = [
        text.strip()
        for heading, text in parser.sections
        if _normalize(heading) == _normalize(section) and text.strip()
    ]
    if not candidates:
        return {"error": "section_not_found", "pep": pep, "section": section, "live_at_call": True}
    text = candidates[-1]
    return {
        "pep": pep,
        "section": section,
        "canonical_url": final_url,
        "status": status,
        "source_digest": f"sha256:{hashlib.sha256(body).hexdigest()}",
        "slice_digest": f"sha256:{hashlib.sha256(text.encode()).hexdigest()}",
        "text_slice": text[:MAX_SLICE_CHARS],
        "slice_truncated": len(text) > MAX_SLICE_CHARS,
        "observed_at": observed,
        "source": {"publisher": "Python PEPs", "format": "text/html"},
        "live_at_call": True,
    }


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()
