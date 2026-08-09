"""Framework-free, allowlisted HTTP HEAD metadata observation."""

from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import urlsplit

from .contract import DEFAULT_TARGET, TARGETS

TIMEOUT_SECONDS = 8
ALLOWED_HOSTS = frozenset(urlsplit(url).hostname for url in TARGETS.values())


class Transport(Protocol):
    def __call__(self, url: str, *, timeout: float) -> tuple[str, int, Mapping[str, str]]: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def _network_head(url: str, *, timeout: float) -> tuple[str, int, Mapping[str, str]]:
    request = urllib.request.Request(
        url,
        method="HEAD",
        headers={"User-Agent": "orrery-http-head/0.1 (+https://github.com/lbliii/orrery)"},
    )
    opener = urllib.request.build_opener(_NoRedirect())
    with opener.open(request, timeout=timeout) as response:
        return response.geturl(), int(response.status), dict(response.headers.items())


def head(
    target: str = DEFAULT_TARGET,
    *,
    transport: Transport = _network_head,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    """Observe only a named target; redirects outside the fixed allowlist fail loud."""
    url = TARGETS.get(target)
    observed_at = (clock or (lambda: datetime.now(UTC)))().isoformat()
    if url is None:
        return {"error": "target_not_allowed", "target": target, "live_at_call": True}
    try:
        final_url, status, headers = transport(url, timeout=TIMEOUT_SECONDS)
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        OSError,
        ValueError,
    ) as error:
        return {
            "error": "upstream_unreachable",
            "target": target,
            "detail": str(error),
            "live_at_call": True,
        }
    final = urlsplit(final_url)
    if final.scheme != "https" or final.hostname not in ALLOWED_HOSTS:
        return {"error": "redirect_not_allowed", "target": target, "live_at_call": True}
    lowered = {str(key).lower(): str(value) for key, value in headers.items()}
    return {
        "target": target,
        "requested_url": url,
        "final_url": final_url,
        "status": status,
        "etag": lowered.get("etag"),
        "last_modified": lowered.get("last-modified"),
        "content_type": lowered.get("content-type"),
        "content_length": lowered.get("content-length"),
        "observed_at": observed_at,
        "live_at_call": True,
    }
