"""Offline contract tests for the external public-domain canary."""

from __future__ import annotations

import json
from typing import Any

import pytest

from discovery import MCP_PROTOCOL_VERSION
from scripts.canary_public_domain import (
    FORBIDDEN_PROTOCOL_VERSION,
    LEGACY_CLIENT_FIXTURES,
    MCP_CONNECT_DEFAULT,
    normalize_origin,
    run,
)

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
                "protocolVersion": MCP_CONNECT_DEFAULT,
                "serverInfo": {"name": "orrery"},
                "transport": {"type": "streamable-http", "endpoint": f"{ORIGIN}/mcp"},
            }
        ).encode(),
    }


def _mcp_response(request: Any, *, initialize_echo: str | None = None) -> bytes | None:
    data = request.data
    if data is None or str(request.full_url) != f"{ORIGIN}/mcp":
        return None
    payload = json.loads(data)
    method = payload.get("method")
    if method == "initialize":
        advertised = payload["params"]["protocolVersion"]
        echoed = initialize_echo if initialize_echo is not None else advertised
        return json.dumps(
            {
                "jsonrpc": "2.0",
                "id": payload.get("id"),
                "result": {"protocolVersion": echoed},
            }
        ).encode()
    if method == "tools/list":
        return json.dumps(
            {
                "jsonrpc": "2.0",
                "id": payload.get("id"),
                "result": {"tools": [{"name": "gaze_match"}]},
            }
        ).encode()
    raise AssertionError(f"unexpected MCP method {method!r}")


def test_canary_accepts_complete_custom_domain_surfaces() -> None:
    pages = _pages()
    run(ORIGIN, opener=_opener(pages))


@pytest.mark.issue(389)
def test_canary_posts_legacy_initialize_pair_after_server_card() -> None:
    pages = _pages()
    posted: list[str] = []
    inner = _opener(pages)

    def open_request(request: Any, *, timeout: int) -> Any:
        data = request.data
        if data is not None:
            payload = json.loads(data)
            if payload.get("method") == "initialize":
                posted.append(payload["params"]["protocolVersion"])
        return inner(request, timeout=timeout)

    run(ORIGIN, opener=open_request)
    assert posted == list(LEGACY_CLIENT_FIXTURES)
    assert MCP_CONNECT_DEFAULT == MCP_PROTOCOL_VERSION


@pytest.mark.issue(389)
def test_canary_fails_closed_when_initialize_echoes_2026_07_28() -> None:
    pages = _pages()
    with pytest.raises(ValueError, match=FORBIDDEN_PROTOCOL_VERSION):
        run(ORIGIN, opener=_opener(pages, initialize_echo=FORBIDDEN_PROTOCOL_VERSION))


@pytest.mark.parametrize(
    ("url", "replacement", "message"),
    [
        (f"{ORIGIN}/", b"<title>Elsewhere</title>", "homepage identity"),
        (f"{ORIGIN}/.well-known/security.txt", b"Contact: x\n", "security.txt missing"),
        (f"{ORIGIN}/.well-known/orrery/trust.json", b'{"version":1,"facts":[]}', "trust document"),
        (f"{ORIGIN}/sitemap.xml", b"<urlset></urlset>", "sitemap"),
        (f"{ORIGIN}/.well-known/mcp/server-card.json", b"{}", "MCP server-card"),
        (
            f"{ORIGIN}/.well-known/mcp/server-card.json",
            json.dumps(
                {
                    "protocolVersion": FORBIDDEN_PROTOCOL_VERSION,
                    "serverInfo": {"name": "orrery"},
                    "transport": {
                        "type": "streamable-http",
                        "endpoint": f"{ORIGIN}/mcp",
                    },
                }
            ).encode(),
            "protocolVersion",
        ),
    ],
)
def test_canary_fails_closed_for_missing_or_incorrect_public_facts(
    url: str, replacement: bytes, message: str
) -> None:
    pages = _pages()
    pages[url] = replacement
    with pytest.raises(ValueError, match=message):
        run(ORIGIN, opener=_opener(pages))


def test_canary_rejects_non_object_trust_document() -> None:
    pages = _pages()
    pages[f"{ORIGIN}/.well-known/orrery/trust.json"] = b"[]"

    with pytest.raises(ValueError, match="top-level shape"):
        run(ORIGIN, opener=_opener(pages))


@pytest.mark.parametrize("origin", ["http://orrery.lol", "https://orrery.lol/path", "https://"])
def test_origin_must_use_normal_bare_https_hostname(origin: str) -> None:
    with pytest.raises(ValueError, match="bare HTTPS"):
        normalize_origin(origin)


def _opener(pages: dict[str, bytes], *, initialize_echo: str | None = None):
    def open_request(request: Any, *, timeout: int) -> _Response:
        assert timeout == 15
        mcp_body = _mcp_response(request, initialize_echo=initialize_echo)
        if mcp_body is not None:
            return _Response(mcp_body)
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
