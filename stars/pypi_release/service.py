from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import urlsplit

from .contract import DEFAULT_PACKAGE, MAX_BYTES, MAX_FILES, PACKAGES

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
    request = urllib.request.Request(url, headers={"User-Agent": "orrery-pypi-release/0.1"})
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
    if package not in PACKAGES:
        return {"error": "package_not_allowed", "package": package, "live_at_call": True}
    url = f"https://pypi.org/pypi/{package}/json"
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
    if parsed.scheme != "https" or parsed.hostname != "pypi.org" or final != url:
        return {"error": "redirect_not_allowed", "package": package, "live_at_call": True}
    if len(body) > MAX_BYTES:
        return {"error": "upstream_too_large", "package": package, "live_at_call": True}
    try:
        record = json.loads(body)
        info = record["info"]
        version = info["version"]
        files = record["releases"][version]
    except UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError:
        return {"error": "source_malformed", "package": package, "live_at_call": True}
    if not isinstance(version, str) or not isinstance(files, list):
        return {"error": "source_malformed", "package": package, "live_at_call": True}
    artifacts = []
    for file in files[:MAX_FILES]:
        if isinstance(file, dict):
            artifacts.append(
                {
                    "filename": file.get("filename"),
                    "upload_time": file.get("upload_time_iso_8601"),
                    "sha256": (file.get("digests") or {}).get("sha256"),
                    "yanked": bool(file.get("yanked", False)),
                }
            )
    result = {
        "package": package,
        "version": version,
        "summary": info.get("summary") if isinstance(info.get("summary"), str) else None,
        "requires_python": info.get("requires_python")
        if isinstance(info.get("requires_python"), str)
        else None,
        "project_urls": _urls(info.get("project_urls")),
        "artifacts": artifacts,
        "artifacts_truncated": len(files) > MAX_FILES,
        "source_url": url,
        "canonical_url": url,
        "status": status,
        "source_digest": f"sha256:{hashlib.sha256(body).hexdigest()}",
        "observed_at": (clock or (lambda: datetime.now(UTC)))().isoformat(),
        "source": {"publisher": "PyPI", "format": "application/json"},
        "live_at_call": True,
    }
    etag = headers.get("ETag") or headers.get("etag")
    if etag:
        result["etag"] = etag
    return result


def _urls(value: object) -> dict[str, str]:
    return (
        {str(k): v[:512] for k, v in value.items() if isinstance(k, str) and isinstance(v, str)}
        if isinstance(value, dict)
        else {}
    )
