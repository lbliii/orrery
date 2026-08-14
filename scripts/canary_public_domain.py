#!/usr/bin/env python3
"""External HTTPS reachability canary for Orrery's public custom domain.

This script intentionally uses only the standard library.  ``urllib`` keeps
normal hostname/TLS validation enabled; do not pin Railway IPs or CNAMEs.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

REQUIRED_SECURITY_FIELDS = ("Contact", "Expires", "Canonical", "Policy")
REQUIRED_TRUST_FACTS = (
    "signed Ed25519 Envelopes",
    "expire after 15 minutes",
    "bounded declared tools",
)

# Duplicated from discovery.MCP_PROTOCOL_VERSION so this script stays stdlib-only.
MCP_CONNECT_DEFAULT = "2025-06-18"
FORBIDDEN_PROTOCOL_VERSION = "2026-07-28"
LEGACY_CLIENT_FIXTURES = ("2025-11-25", "2025-06-18")


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
    headers: dict[str, str] | None = None,
) -> bytes:
    request_headers = dict(headers or {})
    if body is not None:
        request_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(
        url,
        data=body,
        headers=request_headers,
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


def initialize_rpc(client_version: str, request_id: int = 1) -> dict[str, Any]:
    """JSON-RPC initialize body matching the host connect tests (test_app.py)."""
    return {
        "jsonrpc": "2.0",
        "method": "initialize",
        "id": request_id,
        "params": {
            "protocolVersion": client_version,
            "capabilities": {},
            "clientInfo": {"name": "orrery-public-domain-canary", "version": "1"},
        },
    }


def tools_list_rpc(request_id: int = 2) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "method": "tools/list", "id": request_id}


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
    if card.get("protocolVersion") != MCP_CONNECT_DEFAULT:
        raise ValueError(
            f"MCP server-card protocolVersion is not {MCP_CONNECT_DEFAULT}"
        )


def require_initialize_protocol(body: bytes, *, advertised: str) -> None:
    payload = json.loads(body)
    result = payload.get("result") if isinstance(payload, dict) else None
    if not isinstance(result, dict):
        raise ValueError("initialize response has invalid shape")
    version = result.get("protocolVersion")
    if version == FORBIDDEN_PROTOCOL_VERSION:
        raise ValueError(
            f"initialize echoed forbidden protocolVersion {FORBIDDEN_PROTOCOL_VERSION}"
        )
    if version != advertised:
        raise ValueError(
            f"initialize protocolVersion {version!r} does not match {advertised!r}"
        )


def require_gaze_tools(body: bytes) -> None:
    payload = json.loads(body)
    result = payload.get("result") if isinstance(payload, dict) else None
    tools = result.get("tools") if isinstance(result, dict) else None
    if not isinstance(tools, list):
        raise ValueError("tools/list has invalid shape")
    names = {tool.get("name") for tool in tools if isinstance(tool, dict)}
    if "gaze_match" not in names:
        raise ValueError("tools/list missing gaze_match")


def probe_legacy_mcp(
    origin: str, *, opener: Callable[..., Any] = urllib.request.urlopen
) -> None:
    """POST legacy initialize (and tools/list) so /mcp cannot echo 2026-07-28."""
    mcp_url = f"{origin}/mcp"
    for index, client_version in enumerate(LEGACY_CLIENT_FIXTURES, start=1):
        initialized = fetch(
            mcp_url,
            opener=opener,
            body=json.dumps(initialize_rpc(client_version, request_id=index)).encode(),
            headers={"mcp-protocol-version": client_version},
        )
        require_initialize_protocol(initialized, advertised=client_version)
        listed = fetch(
            mcp_url,
            opener=opener,
            body=json.dumps(tools_list_rpc(request_id=index + 100)).encode(),
            headers={"mcp-protocol-version": client_version},
        )
        require_gaze_tools(listed)


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
    probe_legacy_mcp(base, opener=opener)


def maybe_run_catalog_probe(origin: str) -> None:
    """Run the full public catalog MCP probe when ``ORRERY_CANARY_PROBE=1``."""
    if os.environ.get("ORRERY_CANARY_PROBE") != "1":
        return
    repo_root = Path(__file__).resolve().parents[1]
    subprocess.run(
        ["uv", "run", "python", "scripts/probe_all_mcp.py", "--origin", origin],
        cwd=repo_root,
        check=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", default="https://orrery.lol")
    args = parser.parse_args()
    try:
        run(args.origin)
        maybe_run_catalog_probe(args.origin)
    except Exception as error:
        print(f"public-domain canary failed: {error}", file=sys.stderr)
        raise
    print("public-domain canary passed")
