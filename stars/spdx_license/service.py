"""Bounded canonical SPDX license retrieval for a fixed identifier allowlist."""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import urlsplit

from .contract import (
    DEFAULT_LICENSE_ID,
    LICENSE_IDS,
    MAX_BYTES,
    MAX_SEE_ALSO,
    MAX_SEE_ALSO_CHARS,
    MAX_TEXT_CHARS,
)

TIMEOUT_SECONDS = 8
SPDX_HOST = "spdx.org"


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
    request = urllib.request.Request(url, headers={"User-Agent": "orrery-spdx-license/0.1"})
    with urllib.request.build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
        return (
            response.geturl(),
            int(response.status),
            dict(response.headers.items()),
            response.read(max_bytes + 1),
        )


def get(
    license_id: str = DEFAULT_LICENSE_ID,
    *,
    fetch: Fetch = _network_fetch,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    """Retrieve one named SPDX record without accepting caller-controlled URLs."""
    observed = (clock or (lambda: datetime.now(UTC)))().isoformat()
    if license_id not in LICENSE_IDS:
        return {
            "error": "license_not_allowed",
            "license_id": license_id,
            "live_at_call": True,
        }

    source_url = f"https://{SPDX_HOST}/licenses/{license_id}.json"
    human_url = f"https://{SPDX_HOST}/licenses/{license_id}.html"
    try:
        final_url, status, _headers, body = fetch(
            source_url, timeout=TIMEOUT_SECONDS, max_bytes=MAX_BYTES
        )
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        OSError,
        ValueError,
    ) as error:
        return {
            "error": "upstream_unreachable",
            "license_id": license_id,
            "detail": str(error),
            "live_at_call": True,
        }

    final = urlsplit(final_url)
    if final.scheme != "https" or final.hostname != SPDX_HOST or final_url != source_url:
        return {"error": "redirect_not_allowed", "license_id": license_id, "live_at_call": True}
    if len(body) > MAX_BYTES:
        return {"error": "upstream_too_large", "license_id": license_id, "live_at_call": True}
    try:
        record = json.loads(body)
    except UnicodeDecodeError, json.JSONDecodeError:
        return {"error": "source_malformed", "license_id": license_id, "live_at_call": True}
    if not isinstance(record, dict) or record.get("licenseId") != license_id:
        return {"error": "source_malformed", "license_id": license_id, "live_at_call": True}
    license_text = record.get("licenseText")
    if not isinstance(license_text, str):
        return {"error": "source_malformed", "license_id": license_id, "live_at_call": True}

    text_slice = license_text[:MAX_TEXT_CHARS]
    return {
        "license_id": license_id,
        "name": _optional_string(record.get("name")),
        "is_osi_approved": _optional_bool(record.get("isOsiApproved")),
        "is_deprecated_license_id": _optional_bool(record.get("isDeprecatedLicenseId")),
        "see_also": _see_also(record.get("seeAlso")),
        "canonical_url": human_url,
        "source_url": source_url,
        "status": status,
        "source_digest": f"sha256:{hashlib.sha256(body).hexdigest()}",
        "text_digest": f"sha256:{hashlib.sha256(license_text.encode()).hexdigest()}",
        "slice_digest": f"sha256:{hashlib.sha256(text_slice.encode()).hexdigest()}",
        "text_slice": text_slice,
        "slice_truncated": len(license_text) > MAX_TEXT_CHARS,
        "observed_at": observed,
        "source": {"publisher": "SPDX", "format": "application/json"},
        "live_at_call": True,
    }


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _see_also(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item[:MAX_SEE_ALSO_CHARS] for item in value if isinstance(item, str)][:MAX_SEE_ALSO]
