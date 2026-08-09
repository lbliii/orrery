from __future__ import annotations

import base64
import hashlib
import json
import re
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import urlencode, urlsplit

from .contract import DEFAULT_TARGET, MAX_BYTES, MAX_TEXT_CHARS, TARGETS

TIMEOUT_SECONDS = 8
SHA = re.compile(r"^[0-9a-f]{40}$")


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
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "orrery-gh-file-at-ref/0.1",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
        return (
            response.geturl(),
            int(response.status),
            dict(response.headers.items()),
            response.read(max_bytes + 1),
        )


def get(
    target: str = DEFAULT_TARGET,
    ref: str = "",
    *,
    fetch: Fetch = _network_fetch,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    spec = TARGETS.get(target)
    if spec is None:
        return {"error": "target_not_allowed", "target": target, "live_at_call": True}
    if not SHA.fullmatch(ref):
        return {"error": "invalid_ref", "target": target, "ref": ref, "live_at_call": True}
    owner, repo, path = spec
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?{urlencode({'ref': ref})}"
    try:
        final, status, _headers, body = fetch(url, timeout=TIMEOUT_SECONDS, max_bytes=MAX_BYTES)
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
    parsed = urlsplit(final)
    if parsed.scheme != "https" or parsed.hostname != "api.github.com" or final != url:
        return {"error": "redirect_not_allowed", "target": target, "live_at_call": True}
    if len(body) > MAX_BYTES:
        return {"error": "upstream_too_large", "target": target, "live_at_call": True}
    try:
        record = json.loads(body)
        encoded = record["content"]
        if not isinstance(encoded, str):
            raise ValueError("GitHub content must be base64 text")
        raw = base64.b64decode("".join(encoded.split()), validate=True)
        blob = record["sha"]
    except UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError:
        return {"error": "source_malformed", "target": target, "live_at_call": True}
    if not isinstance(blob, str):
        return {"error": "source_malformed", "target": target, "live_at_call": True}
    text = raw.decode("utf-8", errors="replace")
    return {
        "target": target,
        "repo": f"{owner}/{repo}",
        "path": path,
        "requested_ref": ref,
        "blob_sha": blob,
        "canonical_url": f"https://github.com/{owner}/{repo}/blob/{ref}/{path}",
        "source_url": url,
        "status": status,
        "content_digest": f"sha256:{hashlib.sha256(raw).hexdigest()}",
        "text_slice": text[:MAX_TEXT_CHARS],
        "slice_truncated": len(text) > MAX_TEXT_CHARS,
        "content_type": record.get("type"),
        "observed_at": (clock or (lambda: datetime.now(UTC)))().isoformat(),
        "source": {"publisher": "GitHub", "format": "base64 JSON"},
        "live_at_call": True,
    }
