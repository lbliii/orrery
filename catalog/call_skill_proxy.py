"""Same-origin ``call_skill`` forwarder for aggregate ``/mcp`` (ADR 0010)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from chirp.skill import Envelope

from catalog import CATALOG
from catalog.dns import mcp_host

_REGISTRY_BY_PATH: dict[str, Any] = {}


def register_publisher_registry(path: str, registry: Any) -> None:
    """Record a mounted publisher MCP registry for ``call_skill`` forwarding."""
    _REGISTRY_BY_PATH[path] = registry


def mcp_endpoint_path(endpoint: str) -> str | None:
    """Extract the HTTP path from an ``mcp://`` Skill DNS endpoint."""
    if not endpoint.startswith("mcp://"):
        return None
    parsed = urlparse(endpoint.replace("mcp://", "http://", 1))
    if not parsed.path:
        return None
    return parsed.path


def is_same_origin_catalog_endpoint(endpoint: str) -> bool:
    """True when ``endpoint`` is on this host's public Skill DNS apex."""
    if not endpoint.startswith("mcp://"):
        return False
    parsed = urlparse(endpoint.replace("mcp://", "http://", 1))
    host = parsed.hostname or ""
    apex = mcp_host()
    return host == apex or host.endswith(f".{apex}")


def _publisher_registry(app: Any, path: str) -> Any | None:
    del app  # reserved for loopback fallback; registries are registered at mount.
    return _REGISTRY_BY_PATH.get(path)


def _error_response(
    code: str,
    message: str,
    *,
    skill: str = "",
    tool: str = "",
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "status": "error",
        "error": {"code": code, "message": message},
    }
    if skill:
        body["skill"] = skill
    if tool:
        body["tool"] = tool
    return body


def _ok_response(
    skill: str,
    tool: str,
    payload: Any,
    envelope_wire: dict[str, Any] | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "status": "ok",
        "skill": skill,
        "tool": tool,
        "payload": payload,
    }
    if envelope_wire is not None:
        body["envelope_wire"] = envelope_wire
    return body


async def forward_call_skill(
    app: Any,
    *,
    name: str,
    tool: str,
    arguments: dict[str, object] | None = None,
) -> dict[str, Any]:
    """Resolve ``name`` and forward ``tool`` to the same-origin publisher MCP."""
    args = dict(arguments or {})
    record = CATALOG.resolve(name)
    if record is None:
        return _error_response("not_found", f"Unknown skill name: {name}")

    if not is_same_origin_catalog_endpoint(record.endpoint):
        return _error_response(
            "publisher_direct_required",
            "Call the publisher MCP endpoint directly; this host only forwards "
            "same-origin catalog skills.",
            skill=name,
            tool=tool,
        )

    path = mcp_endpoint_path(record.endpoint)
    if path is None:
        return _error_response(
            "publisher_direct_required",
            f"Unsupported endpoint: {record.endpoint!r}",
            skill=name,
            tool=tool,
        )

    publisher = _publisher_registry(app, path)
    if publisher is None:
        return _error_response(
            "publisher_direct_required",
            f"No publisher MCP mounted at {path!r}",
            skill=name,
            tool=tool,
        )

    if publisher.get(tool) is None:
        return _error_response(
            "unknown_tool",
            f"Tool {tool!r} is not on publisher MCP for {name!r}",
            skill=name,
            tool=tool,
        )

    try:
        result = await publisher.call_tool(tool, args)
    except TypeError as exc:
        return _error_response("invalid_arguments", str(exc), skill=name, tool=tool)
    except Exception as exc:
        return _error_response("call_failed", str(exc), skill=name, tool=tool)

    if isinstance(result, Envelope):
        wire = result.to_wire()
        return _ok_response(name, tool, wire.get("payload", {}), wire)

    if isinstance(result, dict):
        return _ok_response(name, tool, result, None)

    return _ok_response(name, tool, {"result": result}, None)
