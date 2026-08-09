"""Compatibility bridge from standard Streamable HTTP MCP to Chirp's router.

Chirp currently treats its internal SEP-2243 routing fields as required for
every modern protocol advertisement.  MCP 2025-06-18 instead puts the
negotiated protocol version in ``MCP-Protocol-Version`` and keeps JSON-RPC
method/name in the request body.  This middleware supplies Chirp-only routing
copies; it never asks a public client to send non-standard headers or metadata.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Collection
from dataclasses import replace
from typing import Any

from chirp import Request
from chirp.http.headers import Headers

_STANDARD_PROTOCOL_VERSIONS = frozenset({"2025-06-18"})
_PROTOCOL_META_KEY = "io.modelcontextprotocol/protocolVersion"

Next = Callable[[Request], Awaitable[Any]]


class StandardMcpCompatibilityMiddleware:
    """Adapt standard MCP 2025-06-18 requests before Chirp dispatches them."""

    def __init__(self, paths: Collection[str]) -> None:
        self._paths = frozenset(paths)

    async def __call__(self, request: Request, next: Next) -> Any:
        if request.path not in self._paths or request.method != "POST":
            return await next(request)
        version = request.headers.get("mcp-protocol-version")
        if version not in _STANDARD_PROTOCOL_VERSIONS:
            return await next(request)
        body = await _standardize_body(request)
        if body is None:
            return await next(request)
        return await next(_chirp_routing_request(request, version, body))


async def _standardize_body(request: Request) -> dict[str, Any] | None:
    """Return only valid JSON-RPC objects; Chirp owns invalid-body responses."""
    try:
        parsed = json.loads(await request.body())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(parsed, dict) or not isinstance(parsed.get("method"), str):
        return None
    # JSON-RPC permits omitted params, and tools/list has no required fields.
    params = parsed.get("params", {})
    if not isinstance(params, dict):
        return None
    meta = params.get("_meta")
    if meta is not None and not isinstance(meta, dict):
        return None
    meta = dict(meta or {})
    # A client-provided body version wins: a disagreement should remain a
    # protocol error instead of silently rewriting a malformed request.
    if _PROTOCOL_META_KEY not in meta:
        meta[_PROTOCOL_META_KEY] = request.headers["mcp-protocol-version"]
    parsed["params"] = {**params, "_meta": meta}
    return parsed


def _chirp_routing_request(request: Request, version: str, body: dict[str, Any]) -> Request:
    """Clone immutable Request state with the internal routing representation."""
    raw = list(request.headers.raw)
    present = {name.lower() for name, _value in raw}
    method = body["method"]
    if b"mcp-method" not in present:
        raw.append((b"mcp-method", method.encode("utf-8")))
    if method == "tools/call" and b"mcp-name" not in present:
        name = body["params"].get("name")
        if isinstance(name, str):
            raw.append((b"mcp-name", name.encode("utf-8")))
    adapted = replace(request, headers=Headers(tuple(raw)))
    adapted._cache["_body"] = json.dumps(body, separators=(",", ":")).encode()
    return adapted
