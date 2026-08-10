#!/usr/bin/env python3
"""External HTTPS reachability canary for Orrery's public custom domain.

This script intentionally uses only the standard library.  ``urllib`` keeps
normal hostname/TLS validation enabled; do not pin Railway IPs or CNAMEs.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

REQUIRED_SECURITY_FIELDS = ("Contact", "Expires", "Canonical", "Policy")
REQUIRED_TRUST_FACTS = (
    "signed Ed25519 Envelopes",
    "expire after 15 minutes",
    "bounded declared tools",
)


def normalize_origin(origin: str) -> str:
    """Accept one HTTPS origin only; all requests use its normal hostname."""
    parsed = urlsplit(origin.strip())
    if parsed.scheme != "https" or not parsed.netloc or parsed.path not in {"", "/"}:
        raise ValueError("origin must be a bare HTTPS origin")
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError("origin must be a bare HTTPS origin")
    return f"https://{parsed.netloc}"


def fetch(
    url: str,
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
    body: bytes | None = None,
) -> bytes:
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    with opener(request, timeout=15) as response:
        status = getattr(response, "status", response.getcode())
        if status != 200:
            raise ValueError(f"unexpected HTTP status {status} for {url}")
        return response.read()


def require_homepage_identity(body: bytes) -> None:
    page = body.decode("utf-8", errors="replace").lower()
    if "<title" not in page or "orrery" not in page or "skills you point at" not in page:
        raise ValueError("homepage identity is missing or incorrect")


def require_security_txt(body: bytes, origin: str) -> None:
    fields: dict[str, str] = {}
    for line in body.decode("utf-8", errors="replace").splitlines():
        key, separator, value = line.partition(":")
        if separator:
            fields[key.strip()] = value.strip()
    missing = [field for field in REQUIRED_SECURITY_FIELDS if not fields.get(field)]
    if missing:
        raise ValueError(f"security.txt missing required fields: {', '.join(missing)}")
    if fields["Canonical"] != f"{origin}/.well-known/security.txt":
        raise ValueError("security.txt Canonical does not match custom origin")
    if fields["Policy"] != f"{origin}/security":
        raise ValueError("security.txt Policy does not match custom origin")


def require_trust_document(body: bytes, origin: str) -> None:
    document = json.loads(body)
    if not isinstance(document, dict):
        raise ValueError("trust document has invalid top-level shape")
    facts = document.get("facts")
    if document.get("version") != 1 or not isinstance(facts, list):
        raise ValueError("trust document has invalid version or facts")
    joined = "\n".join(item for item in facts if isinstance(item, str))
    missing = [fact for fact in REQUIRED_TRUST_FACTS if fact not in joined]
    if missing:
        raise ValueError(f"trust document missing facts: {', '.join(missing)}")
    if document.get("security") != f"{origin}/.well-known/security.txt":
        raise ValueError("trust document security link does not match custom origin")
    if document.get("keys") != f"{origin}/.well-known/orrery/keys.json":
        raise ValueError("trust document keys link does not match custom origin")


def require_sitemap(body: bytes, origin: str) -> None:
    text = body.decode("utf-8", errors="replace")
    if "<urlset" not in text or f"<loc>{origin}/</loc>" not in text:
        raise ValueError("sitemap is missing or does not name the custom origin")


def require_server_card(body: bytes, origin: str) -> None:
    card = json.loads(body)
    transport = card.get("transport") if isinstance(card, dict) else None
    info = card.get("serverInfo") if isinstance(card, dict) else None
    if not isinstance(transport, dict) or not isinstance(info, dict):
        raise ValueError("MCP server-card has invalid shape")
    if info.get("name") != "orrery" or transport.get("type") != "streamable-http":
        raise ValueError("MCP server-card identity is missing or incorrect")
    if transport.get("endpoint") != f"{origin}/mcp":
        raise ValueError("MCP server-card endpoint does not match custom origin")


def run(
    origin: str = "https://orrery.lol", *, opener: Callable[..., Any] = urllib.request.urlopen
) -> None:
    """Check every public reachability/trust surface using hostname-validated TLS."""
    base = normalize_origin(origin)
    require_homepage_identity(fetch(base + "/", opener=opener))
    require_security_txt(fetch(base + "/.well-known/security.txt", opener=opener), base)
    require_trust_document(fetch(base + "/.well-known/orrery/trust.json", opener=opener), base)
    require_sitemap(fetch(base + "/sitemap.xml", opener=opener), base)
    require_server_card(fetch(base + "/.well-known/mcp/server-card.json", opener=opener), base)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", default="https://orrery.lol")
    try:
        run(parser.parse_args().origin)
    except Exception as error:
        print(f"public-domain canary failed: {error}", file=sys.stderr)
        raise
    print("public-domain canary passed")
