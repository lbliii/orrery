from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import urlsplit

from .contract import DEFAULT_PACKAGE, MAX_BYTES, MAX_DEPENDENCIES, PACKAGE_PATHS

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
    request = urllib.request.Request(url, headers={"User-Agent": "orrery-npm-release/0.1"})
    with urllib.request.build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
        return (
            response.geturl(),
            int(response.status),
            dict(response.headers.items()),
            response.read(max_bytes + 1),
        )


def get(
    package: str = DEFAULT_PACKAGE,
    *,
    fetch: Fetch = _network_fetch,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    path = PACKAGE_PATHS.get(package)
    if path is None:
        return {"error": "package_not_allowed", "package": package, "live_at_call": True}
    url = f"https://registry.npmjs.org/{path}"
    try:
        final, status, headers, body = fetch(url, timeout=TIMEOUT_SECONDS, max_bytes=MAX_BYTES)
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        OSError,
        ValueError,
    ) as error:
        return {
            "error": "upstream_unreachable",
            "package": package,
            "detail": str(error),
            "live_at_call": True,
        }
    parsed = urlsplit(final)
    if parsed.scheme != "https" or parsed.hostname != "registry.npmjs.org" or final != url:
        return {"error": "redirect_not_allowed", "package": package, "live_at_call": True}
    if len(body) > MAX_BYTES:
        return {"error": "upstream_too_large", "package": package, "live_at_call": True}
    try:
        record = json.loads(body)
        dist = record["dist"]
        name = record["name"]
        version = record["version"]
    except UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError:
        return {"error": "source_malformed", "package": package, "live_at_call": True}
    if name != package or not isinstance(version, str) or not isinstance(dist, dict):
        return {"error": "source_malformed", "package": package, "live_at_call": True}
    deps = record.get("dependencies")
    dependencies = (
        {
            k: v
            for k, v in list(deps.items())[:MAX_DEPENDENCIES]
            if isinstance(k, str) and isinstance(v, str)
        }
        if isinstance(deps, dict)
        else {}
    )
    result = {
        "package": package,
        "name": name,
        "version": version,
        "description": record.get("description")
        if isinstance(record.get("description"), str)
        else None,
        "license": record.get("license") if isinstance(record.get("license"), str) else None,
        "engines": record.get("engines") if isinstance(record.get("engines"), dict) else {},
        "dist": {
            "tarball": dist.get("tarball"),
            "integrity": dist.get("integrity"),
            "shasum": dist.get("shasum"),
        },
        "dependencies": dependencies,
        "dependencies_truncated": isinstance(deps, dict) and len(deps) > MAX_DEPENDENCIES,
        "source_url": url,
        "canonical_url": url,
        "status": status,
        "source_digest": f"sha256:{hashlib.sha256(body).hexdigest()}",
        "observed_at": (clock or (lambda: datetime.now(UTC)))().isoformat(),
        "source": {"publisher": "npm", "format": "application/json"},
        "live_at_call": True,
    }
    etag = headers.get("ETag") or headers.get("etag")
    if etag:
        result["etag"] = etag
    return result
