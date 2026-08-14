"""ADR 0010 structured JSON for MCP ``tools/call`` ``content[].text`` (#391)."""

from __future__ import annotations

import functools
import inspect
import re
from collections.abc import Callable
from typing import Any

from chirp.skill import Envelope

from catalog.constellation_run import pause_resume_contract

_SNAKE_CASE_CODE = re.compile(r"^[a-z][a-z0-9_]*$")
#: Chirp ``Skill.tool`` auto-seals author dicts. Discovery misses must stay
#: unsigned MCP errors (ADR 0011) without turning managed ``run_not_found``
#: seals into ``status: "error"``.
_DISCOVERY_MISS_TOOLS = frozenset({"resolve_name", "gaze_describe"})


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
    if isinstance(payload, dict):
        pause = pause_resume_contract(payload)
        if pause is not None:
            body.update(pause)
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


def _is_unsigned_snake_error(result: dict[str, Any]) -> bool:
    """True when *result* is an unsigned handler dict with a snake_case ``error`` code."""
    if "signature" in result:
        return False
    error = result.get("error")
    return isinstance(error, str) and bool(error) and _SNAKE_CASE_CODE.fullmatch(error) is not None


def _unsigned_error_message(result: dict[str, Any], code: str) -> str:
    """Caller-safe MCP error message; never exception text."""
    for key in ("detail", "message"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    name = result.get("name")
    if code == "not_found" and isinstance(name, str) and name.strip():
        return f"Skill not found: {name.strip()}"
    return code.replace("_", " ")


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
        if _is_unsigned_snake_error(result):
            code = str(result["error"])
            return mcp_error_response(
                code,
                _unsigned_error_message(result, code),
                skill=skill,
                tool=tool,
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
    author = getattr(handler, "__wrapped__", None)

    def _unsigned_discovery_miss(raw: Any) -> dict[str, Any] | None:
        if tool not in _DISCOVERY_MISS_TOOLS:
            return None
        if not isinstance(raw, dict) or not _is_unsigned_snake_error(raw):
            return None
        return structured_tool_body(raw, skill=skill, tool=tool)

    if inspect.iscoroutinefunction(handler):

        @functools.wraps(handler)
        async def async_wrapped(*args: Any, **kwargs: Any) -> dict[str, Any]:
            if author is not None and tool in _DISCOVERY_MISS_TOOLS:
                raw = (
                    await author(*args, **kwargs)
                    if inspect.iscoroutinefunction(author)
                    else author(*args, **kwargs)
                )
                miss = _unsigned_discovery_miss(raw)
                if miss is not None:
                    return miss
            result = await handler(*args, **kwargs)
            return structured_tool_body(result, skill=skill, tool=tool)

        return async_wrapped

    @functools.wraps(handler)
    def sync_wrapped(*args: Any, **kwargs: Any) -> dict[str, Any]:
        if author is not None and tool in _DISCOVERY_MISS_TOOLS:
            miss = _unsigned_discovery_miss(author(*args, **kwargs))
            if miss is not None:
                return miss
        result = handler(*args, **kwargs)
        return structured_tool_body(result, skill=skill, tool=tool)

    return sync_wrapped
