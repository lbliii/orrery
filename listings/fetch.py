"""SSRF-safe HTTPS fetch for a single submitted listing URL (ADR 0012)."""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .schema import ListingError

MAX_BYTES = 64 * 1024
FETCH_TIMEOUT_S = 8
_BLOCKED_HOSTS = frozenset({"localhost", "localhost.localdomain"})


def assert_public_https_url(url: str) -> None:
    """Reject non-HTTPS, credentials, and names that resolve privately."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ListingError("https_only", "listing URL must be https")
    if parsed.username or parsed.password:
        raise ListingError("https_only", "listing URL must not include credentials")
    host = (parsed.hostname or "").lower()
    if not host or host in _BLOCKED_HOSTS:
        raise ListingError("private_address", "listing host is not a public name")
    if parsed.port not in (None, 443):
        raise ListingError("https_only", "listing URL must use port 443")
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ListingError("fetch_failed", f"could not resolve {host}") from exc
    for info in infos:
        ip_text = info[4][0]
        _reject_private_ip(ip_text)


def fetch_listing_bytes(url: str) -> bytes:
    """GET ``url`` with no redirects, 64 KiB cap, public HTTPS only."""
    assert_public_https_url(url)
    request = Request(url, method="GET", headers={"Accept": "application/json, */*"})
    try:
        with urlopen(request, timeout=FETCH_TIMEOUT_S) as response:
            if response.geturl() != url:
                raise ListingError("https_only", "redirects are not allowed")
            return response.read(MAX_BYTES + 1)
    except ListingError:
        raise
    except Exception as exc:
        raise ListingError("fetch_failed", "could not fetch listing URL") from exc


def fetch_and_cap(url: str, *, fetch: Callable[[str], bytes] | None = None) -> bytes:
    """Fetch and enforce the 64 KiB cap.

    Scheme is checked even when ``fetch`` is injected so tests and ping
    reject ``http://`` without resolving a host.
    """
    parsed_scheme = urlparse(url).scheme
    if parsed_scheme != "https":
        raise ListingError("https_only", "listing URL must be https")
    raw = (fetch or fetch_listing_bytes)(url)
    if len(raw) > MAX_BYTES:
        raise ListingError("too_large", "listing exceeds 64 KiB")
    return raw


def _reject_private_ip(ip_text: str) -> None:
    try:
        addr = ipaddress.ip_address(ip_text)
    except ValueError as exc:
        raise ListingError("private_address", "invalid resolved address") from exc
    if (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    ):
        raise ListingError("private_address", "listing host resolved to a private address")
