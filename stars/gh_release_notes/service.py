from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import urlsplit

from .contract import DEFAULT_TARGET, MAX_BYTES, MAX_NOTES, TARGETS

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
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "orrery-gh-release-notes/0.1",
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


def observe(
    target: str = DEFAULT_TARGET,
    prior_body_digest: str = "",
    *,
    fetch: Fetch = _network_fetch,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    spec = TARGETS.get(target)
    if spec is None:
        return {"error": "target_not_allowed", "target": target, "live_at_call": True}
    if not isinstance(prior_body_digest, str) or len(prior_body_digest) > 100:
        return {"error": "invalid_prior_digest", "target": target, "live_at_call": True}
    owner, repo = spec
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
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
        notes = record.get("body", "")
        release_id = record["id"]
        tag = record["tag_name"]
    except UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError:
        return {"error": "source_malformed", "target": target, "live_at_call": True}
    if not isinstance(notes, str) or not isinstance(tag, str):
        return {"error": "source_malformed", "target": target, "live_at_call": True}
    digest = f"sha256:{hashlib.sha256(notes.encode()).hexdigest()}"
    change = (
        "unknown"
        if not prior_body_digest
        else ("unchanged" if prior_body_digest == digest else "changed")
    )
    result = {
        "target": target,
        "repo": f"{owner}/{repo}",
        "release_id": release_id,
        "tag": tag,
        "name": record.get("name"),
        "published_at": record.get("published_at"),
        "html_url": record.get("html_url"),
        "draft": bool(record.get("draft", False)),
        "prerelease": bool(record.get("prerelease", False)),
        "body_digest": digest,
        "notes_slice": notes[:MAX_NOTES],
        "notes_truncated": len(notes) > MAX_NOTES,
        "change": change,
        "source_url": url,
        "canonical_url": url,
        "status": status,
        "source_digest": f"sha256:{hashlib.sha256(body).hexdigest()}",
        "observed_at": (clock or (lambda: datetime.now(UTC)))().isoformat(),
        "source": {"publisher": "GitHub", "format": "application/json"},
        "live_at_call": True,
    }
    etag = headers.get("ETag") or headers.get("etag")
    if etag:
        result["etag"] = etag
    return result
