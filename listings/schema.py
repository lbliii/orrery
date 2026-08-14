"""orrery-listing/0.1 parse + validation (ADR 0012)."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from namespaces.validation import RESERVED_SLUGS, is_valid_slug, normalize_slug

LISTING_SPEC = "orrery-listing/0.1"
MAX_USE_WHEN = 3
MAX_SUMMARY_LEN = 280
MAX_TOOLS = 24
SLUG_FROM_NAME = re.compile(r"^[a-z][a-z0-9-]{1,62}$")


class ListingError(ValueError):
    """Invalid listing document or intake."""

    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(message or code)


@dataclass(frozen=True, slots=True)
class ListingDocument:
    """Validated listing file (desired name + publisher coordinates)."""

    spec: str
    desired_name: str
    slug: str
    live_name: str
    summary: str
    use_when: tuple[str, ...]
    endpoint: str
    transport: str
    tools: tuple[str, ...]
    content_digest: str
    price_per_call: str | None = None
    key_id: str | None = None
    alg: str = "Ed25519"
    contact: str | None = None
    inputs_summary: str | None = None
    listing_url: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "spec": self.spec,
            "name": self.desired_name,
            "live_name": self.live_name,
            "summary": self.summary,
            "use_when": list(self.use_when),
            "endpoint": self.endpoint,
            "transport": self.transport,
            "tools": list(self.tools),
            "content_digest": self.content_digest,
            "price_per_call": self.price_per_call,
            "key_id": self.key_id,
            "alg": self.alg,
            "contact": self.contact,
            "inputs_summary": self.inputs_summary,
        }


def listing_digest(raw: bytes) -> str:
    """sha256 of the listing bytes (not a Chirp skill digest)."""
    return hashlib.sha256(raw).hexdigest()


def slug_for_desired_name(desired: str) -> str:
    """``publisher/invoice-check`` → ``invoice-check``."""
    name = (desired or "").strip().lower()
    if "/" not in name:
        raise ListingError("invalid_name", "name must be namespace/slug")
    ns, slug = name.split("/", 1)
    ns = normalize_slug(ns)
    slug = normalize_slug(slug)
    if ns in RESERVED_SLUGS:
        raise ListingError("reserved_name", f"cannot claim reserved prefix {ns!r}")
    if not is_valid_slug(ns) or not SLUG_FROM_NAME.fullmatch(slug):
        raise ListingError("invalid_name", "namespace and slug must be DNS labels")
    return slug


def parse_listing(raw: bytes, *, listing_url: str | None = None) -> ListingDocument:
    """Parse and validate listing JSON bytes."""
    if len(raw) > 64 * 1024:
        raise ListingError("too_large", "listing exceeds 64 KiB")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ListingError("invalid_listing", "listing is not UTF-8 JSON") from exc
    if not isinstance(data, dict):
        raise ListingError("invalid_listing", "listing must be a JSON object")

    spec = str(data.get("spec") or "").strip()
    if spec != LISTING_SPEC:
        raise ListingError("invalid_listing", f"spec must be {LISTING_SPEC}")

    desired = str(data.get("name") or "").strip()
    slug = slug_for_desired_name(desired)
    summary = str(data.get("summary") or "").strip()
    if not summary or len(summary) > MAX_SUMMARY_LEN:
        raise ListingError("invalid_listing", "summary required (<=280 chars)")

    use_when = _string_tuple(data.get("use_when"), field="use_when")
    if not use_when or len(use_when) > MAX_USE_WHEN:
        raise ListingError("invalid_listing", "use_when must have 1-3 bullets")

    endpoint = str(data.get("endpoint") or "").strip()
    _require_https_url(endpoint, field="endpoint")
    transport = str(data.get("transport") or "streamable-http").strip()
    if transport != "streamable-http":
        raise ListingError("invalid_listing", "transport must be streamable-http")

    tools = _string_tuple(data.get("tools"), field="tools")
    if not tools or len(tools) > MAX_TOOLS:
        raise ListingError("invalid_listing", "tools must list 1-24 names")

    price = data.get("price_per_call")
    key_id = data.get("key_id")
    contact = data.get("contact")
    inputs = data.get("inputs_summary")
    alg = str(data.get("alg") or "Ed25519").strip() or "Ed25519"

    return ListingDocument(
        spec=spec,
        desired_name=desired.lower(),
        slug=slug,
        live_name=f"new/{slug}",
        summary=summary,
        use_when=use_when,
        endpoint=endpoint,
        transport=transport,
        tools=tools,
        content_digest=listing_digest(raw),
        price_per_call=None if price in (None, "") else str(price),
        key_id=None if key_id in (None, "") else str(key_id),
        alg=alg,
        contact=None if contact in (None, "") else str(contact),
        inputs_summary=None if inputs in (None, "") else str(inputs),
        listing_url=listing_url,
    )


def assert_proof_of_control(listing_url: str, endpoint: str) -> None:
    """Listing URL host and endpoint host must share a registrable domain."""
    listing_host = _hostname(listing_url)
    endpoint_host = _hostname(endpoint)
    if _registrable(listing_host) != _registrable(endpoint_host):
        raise ListingError(
            "proof_of_control",
            "listing URL host and endpoint host must share a domain",
        )


def _string_tuple(value: Any, *, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ListingError("invalid_listing", f"{field} must be an array of strings")
    out: list[str] = []
    for item in value:
        text = str(item).strip()
        if not text:
            raise ListingError("invalid_listing", f"{field} entries must be non-empty")
        out.append(text)
    return tuple(out)


def _require_https_url(url: str, *, field: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc or not parsed.hostname:
        raise ListingError("invalid_listing", f"{field} must be an https URL")


def _hostname(url: str) -> str:
    host = urlparse(url).hostname
    if not host:
        raise ListingError("invalid_listing", "URL missing host")
    return host.lower()


def _registrable(host: str) -> str:
    parts = host.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host
