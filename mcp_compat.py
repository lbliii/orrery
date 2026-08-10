"""Compatibility bridge from standard Streamable HTTP MCP to Chirp's router.

Chirp currently treats its internal SEP-2243 routing fields as required for
every modern protocol advertisement.  MCP 2025-06-18 instead puts the
negotiated protocol version in ``MCP-Protocol-Version`` and keeps JSON-RPC
method/name in the request body.  This middleware supplies Chirp-only routing
copies; it never asks a public client to send non-standard headers or metadata.

Chirp's ``initialize`` handler always advertises ``2026-07-28``.  Standard
clients (Cursor, Claude Code, …) expect the negotiated version to be echoed
back.  This middleware rewrites successful ``initialize`` responses for
standard protocol advertisements.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Collection
from dataclasses import replace
from typing import Any

from chirp import Request
from chirp.http.headers import Headers
from chirp.http.response import Response

_STANDARD_PROTOCOL_VERSIONS = frozenset({"2025-06-18"})
_PROTOCOL_META_KEY = "io.modelcontextprotocol/protocolVersion"
_LEGACY_OFFRAMP_META_KEY = "chirp/legacyOfframp"

Next = Callable[[Request], Awaitable[Any]]


class StandardMcpCompatibilityMiddleware:
    """Adapt standard MCP 2025-06-18 requests before Chirp dispatches them."""

    def __init__(self, paths: Collection[str]) -> None:
        self._paths = frozenset(paths)

    async def __call__(self, request: Request, next: Next) -> Any:
        if request.path not in self._paths or request.method != "POST":
            return await next(request)
        body = await _parse_jsonrpc_body(request)
        if body is None:
            return await next(request)
        standard_version = _negotiated_standard_version(request, body)
        if standard_version is None:
            return await next(request)
        forward = _chirp_routing_request(request, standard_version, body)
        response = await next(forward)
        if body["method"] == "initialize":
            return _adapt_initialize_response(response, standard_version)
        return response


def _negotiated_standard_version(request: Request, body: dict[str, Any]) -> str | None:
    """Return the MCP 2025-06-18 version when the client advertises it."""
    header = request.headers.get("mcp-protocol-version")
    if header in _STANDARD_PROTOCOL_VERSIONS:
        return header
    params = body.get("params")
    if isinstance(params, dict):
        body_version = params.get("protocolVersion")
        if isinstance(body_version, str) and body_version in _STANDARD_PROTOCOL_VERSIONS:
            return body_version
    return None


async def _parse_jsonrpc_body(request: Request) -> dict[str, Any] | None:
    """Return only valid JSON-RPC objects; Chirp owns invalid-body responses."""
    try:
        parsed = json.loads(await request.body())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(parsed, dict) or not isinstance(parsed.get("method"), str):
        return None
    params = parsed.get("params", {})
    if params != {} and not isinstance(params, dict):
        return None
    meta = params.get("_meta") if isinstance(params, dict) else None
    if meta is not None and not isinstance(meta, dict):
        return None
    return parsed


def _standardize_body(standard_version: str, body: dict[str, Any]) -> dict[str, Any]:
    """Inject Chirp ``params._meta`` protocol version for routing validation."""
    params = body.get("params", {})
    assert isinstance(params, dict)
    meta = params.get("_meta")
    meta = dict(meta or {})
    # A client-provided body _meta version wins: disagreement stays a protocol
    # error instead of silently rewriting a malformed request.
    if _PROTOCOL_META_KEY not in meta:
        meta[_PROTOCOL_META_KEY] = standard_version
    return {**body, "params": {**params, "_meta": meta}}


def _chirp_routing_request(
    request: Request,
    standard_version: str,
    body: dict[str, Any],
) -> Request:
    """Clone immutable Request state with the internal routing representation."""
    body = _standardize_body(standard_version, body)
    raw = list(request.headers.raw)
    present = {name.lower() for name, _value in raw}
    if b"mcp-protocol-version" not in present:
        raw.append((b"mcp-protocol-version", standard_version.encode("utf-8")))
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


def _adapt_initialize_response(response: Any, negotiated_version: str) -> Any:
    """Echo the client's standard protocol version on ``initialize`` success."""
    if not isinstance(response, Response) or response.status != 200:
        return response
    try:
        payload = response.json
    except ValueError:
        return response
    if not isinstance(payload, dict):
        return response
    result = payload.get("result")
    if not isinstance(result, dict) or "protocolVersion" not in result:
        return response
    if result.get("protocolVersion") == negotiated_version:
        return response

    new_result = dict(result)
    new_result["protocolVersion"] = negotiated_version
    meta = new_result.get("_meta")
    if isinstance(meta, dict):
        new_meta = dict(meta)
        new_meta.pop(_LEGACY_OFFRAMP_META_KEY, None)
        new_result["_meta"] = new_meta

    new_payload = {**payload, "result": new_result}
    encoded = json.dumps(new_payload, separators=(",", ":")).encode()
    return replace(response, body=encoded)
