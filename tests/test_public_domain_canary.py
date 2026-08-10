"""Offline contract tests for the external public-domain canary."""

from __future__ import annotations

import json
from typing import Any

import pytest

from scripts.canary_public_domain import normalize_origin, run

ORIGIN = "https://orrery.lol"


def _pages() -> dict[str, bytes]:
    return {
        f"{ORIGIN}/": b"<html><title>Orrery</title>Skills you point at, not install.</html>",
        f"{ORIGIN}/.well-known/security.txt": (
            f"Contact: https://github.com/lbliii/orrery/security/advisories/new\n"
            f"Canonical: {ORIGIN}/.well-known/security.txt\n"
            "Preferred-Languages: en\n"
            f"Policy: {ORIGIN}/security\nExpires: 2027-01-01T00:00:00.000Z\n"
        ).encode(),
        f"{ORIGIN}/.well-known/orrery/trust.json": json.dumps(
            {
                "version": 1,
                "facts": [
                    "Public results are signed Ed25519 Envelopes.",
                    "Artifact downloads expire after 15 minutes.",
                    "Public Stars expose bounded declared tools.",
                ],
                "security": f"{ORIGIN}/.well-known/security.txt",
                "keys": f"{ORIGIN}/.well-known/orrery/keys.json",
            }
        ).encode(),
        f"{ORIGIN}/sitemap.xml": f"<urlset><url><loc>{ORIGIN}/</loc></url></urlset>".encode(),
        f"{ORIGIN}/.well-known/mcp/server-card.json": json.dumps(
            {
                "serverInfo": {"name": "orrery"},
                "transport": {"type": "streamable-http", "endpoint": f"{ORIGIN}/mcp"},
            }
        ).encode(),
    }


def test_canary_accepts_complete_custom_domain_surfaces() -> None:
    pages = _pages()
    run(ORIGIN, opener=_opener(pages))


@pytest.mark.parametrize(
    ("url", "replacement", "message"),
    [
        (f"{ORIGIN}/", b"<title>Elsewhere</title>", "homepage identity"),
        (f"{ORIGIN}/.well-known/security.txt", b"Contact: x\n", "security.txt missing"),
        (f"{ORIGIN}/.well-known/orrery/trust.json", b'{"version":1,"facts":[]}', "trust document"),
        (f"{ORIGIN}/sitemap.xml", b"<urlset></urlset>", "sitemap"),
        (f"{ORIGIN}/.well-known/mcp/server-card.json", b"{}", "MCP server-card"),
    ],
)
def test_canary_fails_closed_for_missing_or_incorrect_public_facts(
    url: str, replacement: bytes, message: str
) -> None:
    pages = _pages()
    pages[url] = replacement
    with pytest.raises(ValueError, match=message):
        run(ORIGIN, opener=_opener(pages))


@pytest.mark.parametrize("origin", ["http://orrery.lol", "https://orrery.lol/path", "https://"])
def test_origin_must_use_normal_bare_https_hostname(origin: str) -> None:
    with pytest.raises(ValueError, match="bare HTTPS"):
        normalize_origin(origin)


def _opener(pages: dict[str, bytes]):
    def open_request(request: Any, *, timeout: int) -> _Response:
        assert timeout == 15
        url = str(request.full_url)
        return _Response(pages[url])

    return open_request


class _Response:
    status = 200

    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def getcode(self) -> int:
        return self.status

    def read(self) -> bytes:
        return self._body
