"""Bounded, allowlisted link checks over caller markdown/html bundles."""

from __future__ import annotations

import re
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any, Protocol
from urllib.parse import urlsplit

from .contract import (
    ALLOWED_ORIGINS,
    DEFAULT_MAX_LINK_COUNT,
    MAX_CONTENT_BYTES,
    MAX_FILES,
    MAX_LINK_COUNT_CAP,
    MAX_PATH_LEN,
    TIMEOUT_SECONDS,
)

_MD_LINK_RE = re.compile(r"\[[^\]]*\]\((https?://[^)\s]+)\)")
_HTML_HREF_RE = re.compile(
    r"""href\s*=\s*["'](https?://[^"']+)["']""",
    re.IGNORECASE,
)
_PATH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
ALLOWED_HOSTS = frozenset(urlsplit(origin).hostname for origin in ALLOWED_ORIGINS)


class Transport(Protocol):
    def __call__(self, url: str, *, timeout: float) -> tuple[str, int]: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def _network_head(url: str, *, timeout: float) -> tuple[str, int]:
    request = urllib.request.Request(
        url,
        method="HEAD",
        headers={"User-Agent": "orrery-link-check-bounded/0.1 (+https://github.com/lbliii/orrery)"},
    )
    opener = urllib.request.build_opener(_NoRedirect())
    with opener.open(request, timeout=timeout) as response:
        return response.geturl(), int(response.status)


def check(
    files: object,
    max_link_count: object = DEFAULT_MAX_LINK_COUNT,
    *,
    transport: Transport = _network_head,
) -> dict[str, object]:
    """Extract links, fail loud over cap, and HEAD only allowlisted HTTPS origins."""
    if (
        isinstance(max_link_count, bool)
        or not isinstance(max_link_count, int)
        or max_link_count < 1
        or max_link_count > MAX_LINK_COUNT_CAP
    ):
        return {"error": "max_link_count_invalid", "max_link_count": max_link_count}

    parsed_files, parse_error = _parse_files(files)
    if parse_error is not None:
        return parse_error

    assert parsed_files is not None
    extracted: list[dict[str, str]] = []
    for entry in parsed_files:
        for url in _extract_links(entry["content"], entry["format"]):
            extracted.append({"path": entry["path"], "url": url})

    if len(extracted) > max_link_count:
        return {
            "error": "link_count_exceeded",
            "link_count": len(extracted),
            "max_link_count": max_link_count,
        }

    results: list[dict[str, object]] = []
    egress_count = 0
    for item in extracted:
        url = item["url"]
        status = _status_for(url, transport=transport)
        if status.get("egress"):
            egress_count += 1
        results.append(
            {
                "path": item["path"],
                "url": url,
                "status": status["status"],
                **(
                    {"http_status": status["http_status"]}
                    if "http_status" in status
                    else {}
                ),
                **({"detail": status["detail"]} if "detail" in status else {}),
            }
        )

    ok_count = sum(1 for row in results if row["status"] == "ok")
    return {
        "links": results,
        "link_count": len(results),
        "max_link_count": max_link_count,
        "ok_count": ok_count,
        "egress_count": egress_count,
        "passed": ok_count == len(results),
        "live_at_call": egress_count > 0,
    }


def _parse_files(
    files: object,
) -> tuple[list[dict[str, str]] | None, dict[str, object] | None]:
    if not isinstance(files, list) or not files or len(files) > MAX_FILES:
        return None, {"error": "files_invalid"}

    parsed: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, raw in enumerate(files):
        if not isinstance(raw, Mapping):
            return None, {"error": "entry_not_object", "index": index}
        if set(raw) - {"path", "content", "format"}:
            return None, {"error": "entry_unknown_fields", "index": index}

        path = raw.get("path")
        content = raw.get("content")
        fmt = raw.get("format", "markdown")
        if not isinstance(path, str) or not path or len(path) > MAX_PATH_LEN:
            return None, {"error": "path_invalid", "index": index}
        if path.startswith("/") or path.startswith("../") or "/../" in f"/{path}/":
            return None, {"error": "path_traversal", "path": path, "index": index}
        if not _PATH_RE.fullmatch(path):
            return None, {"error": "path_invalid", "path": path, "index": index}
        if path in seen:
            return None, {"error": "duplicate_path", "path": path, "index": index}
        if not isinstance(content, str):
            return None, {"error": "content_invalid", "path": path, "index": index}
        if len(content.encode()) > MAX_CONTENT_BYTES:
            return None, {"error": "content_too_large", "path": path, "index": index}
        if fmt not in {"markdown", "html"}:
            return None, {"error": "format_invalid", "path": path, "index": index}
        seen.add(path)
        parsed.append({"path": path, "content": content, "format": str(fmt)})
    return parsed, None


def _extract_links(content: str, fmt: str) -> list[str]:
    if fmt == "html":
        return _HTML_HREF_RE.findall(content)
    return _MD_LINK_RE.findall(content)


def _status_for(url: str, *, transport: Transport) -> dict[str, object]:
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        return {"status": "not_allowed", "egress": False}
    origin = f"{parts.scheme}://{parts.hostname}"
    if origin not in ALLOWED_ORIGINS and parts.hostname not in ALLOWED_HOSTS:
        return {"status": "not_allowed", "egress": False}
    try:
        final_url, http_status = transport(url, timeout=TIMEOUT_SECONDS)
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        OSError,
        ValueError,
    ) as error:
        return {"status": "unreachable", "detail": str(error), "egress": True}

    final = urlsplit(final_url)
    if final.scheme != "https" or final.hostname not in ALLOWED_HOSTS:
        return {"status": "redirect_not_allowed", "egress": True}
    return {"status": "ok", "http_status": http_status, "egress": True}
