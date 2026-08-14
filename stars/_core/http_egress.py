"""Shared HTTPS transport for public networked stars (A-tier practice 4).

Rejects redirects at the urllib handler so a 3xx cannot silently hop hosts.
Allowlists, User-Agent, and payload ``{error, live_at_call}`` codes stay
per-star — this module is transport only.

See ``docs/design/caller-trust-a-tier.md`` and ADR 0011.
"""

from __future__ import annotations

import urllib.request
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from http.client import HTTPResponse
from typing import Any


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse to follow redirects; urllib then surfaces HTTPError on 3xx."""

    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


@contextmanager
def open_https(
    request: urllib.request.Request, *, timeout: float
) -> Iterator[HTTPResponse]:
    """Open ``request`` once with redirects disabled."""
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(request, timeout=timeout) as response:
        yield response


def https_head(
    url: str, *, timeout: float, headers: Mapping[str, str]
) -> tuple[str, int, dict[str, str]]:
    """Bounded HTTPS HEAD. Caller still enforces its own host allowlist."""
    request = urllib.request.Request(url, method="HEAD", headers=dict(headers))
    with open_https(request, timeout=timeout) as response:
        return response.geturl(), int(response.status), dict(response.headers.items())


def https_get(
    url: str, *, timeout: float, max_bytes: int, headers: Mapping[str, str]
) -> tuple[str, int, dict[str, str], bytes]:
    """Bounded HTTPS GET. Reads at most ``max_bytes + 1`` so callers can detect overflow."""
    request = urllib.request.Request(url, headers=dict(headers))
    with open_https(request, timeout=timeout) as response:
        return (
            response.geturl(),
            int(response.status),
            dict(response.headers.items()),
            response.read(max_bytes + 1),
        )
