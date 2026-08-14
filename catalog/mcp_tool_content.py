"""ADR 0010 structured JSON for MCP ``tools/call`` ``content[].text`` (#391)."""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import Any

from chirp.skill import Envelope


def mcp_error_response(
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


def mcp_ok_response(
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


def is_structured_mcp_body(value: Any) -> bool:
    """True when *value* is already an ADR 0010 ``content[].text`` object."""
    if not isinstance(value, dict):
        return False
    status = value.get("status")
    if status == "error":
        return isinstance(value.get("error"), dict)
    if status == "ok":
        return "payload" in value
    return False


def structured_tool_body(
    result: Any,
    *,
    skill: str = "",
    tool: str = "",
) -> dict[str, Any]:
    """Convert a tool handler result into ADR 0010 JSON (not ``Envelope`` repr)."""
    if is_structured_mcp_body(result):
        return result

    if isinstance(result, Envelope):
        wire = result.to_wire()
        payload = wire.get("payload", {})
        return mcp_ok_response(
            skill or str(wire.get("skill", "")),
            tool or str(wire.get("tool", "")),
            payload,
            wire,
        )

    if isinstance(result, dict):
        if "signature" in result and "payload" in result:
            return mcp_ok_response(
                skill or str(result.get("skill", "")),
                tool or str(result.get("tool", "")),
                result.get("payload", {}),
                result,
            )
        if skill and tool:
            return mcp_ok_response(skill, tool, result, None)
        return mcp_ok_response(skill or "", tool or "", result, None)

    return mcp_ok_response(skill or "", tool or "", {"result": result}, None)


def wrap_structured_mcp_handler(
    handler: Callable[..., Any],
    *,
    skill: str,
    tool: str,
) -> Callable[..., Any]:
    """Wrap a signed skill tool so MCP returns structured JSON instead of ``Envelope`` repr."""

    if inspect.iscoroutinefunction(handler):

        @functools.wraps(handler)
        async def async_wrapped(*args: Any, **kwargs: Any) -> dict[str, Any]:
            result = await handler(*args, **kwargs)
            return structured_tool_body(result, skill=skill, tool=tool)

        return async_wrapped

    @functools.wraps(handler)
    def sync_wrapped(*args: Any, **kwargs: Any) -> dict[str, Any]:
        result = handler(*args, **kwargs)
        return structured_tool_body(result, skill=skill, tool=tool)

    return sync_wrapped
