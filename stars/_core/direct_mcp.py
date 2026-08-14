"""Direct, per-Star MCP endpoints backed by a canonical Star skill.

The aggregate host has one flat MCP tool namespace.  A Star's direct endpoint
does not: it exposes the package's natural tool names and uses the same Chirp
JSON-RPC handler as the host MCP surface.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

from chirp.http.request import Request
from chirp.http.response import Response
from chirp.skill import Skill
from chirp.tools.handler import handle_mcp_request
from chirp.tools.registry import ToolDef, ToolRegistry
from chirp.tools.schema import function_to_schema

from catalog.mcp_tool_content import wrap_structured_mcp_handler

from .definition import StarDefinition

if TYPE_CHECKING:
    from chirp import App


def _normalize_contracts(raw: object) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for name, value in raw.items():
        if not isinstance(name, str) or not isinstance(value, dict):
            continue
        description = value.get("description")
        schema = value.get("inputSchema")
        if not isinstance(schema, dict):
            schema = {"type": "object", "properties": {}}
        out[name] = {
            "description": description if isinstance(description, str) else f"Call {name}.",
            "inputSchema": schema,
        }
    return out


def _load_contract_schemas(python_package: str) -> dict[str, dict[str, Any]]:
    """Load published ``tool_schemas()`` from a star package when present."""
    for module_name in (python_package, f"{python_package}.contract"):
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
        raw = getattr(module, "tool_schemas", None)
        if callable(raw):
            return _normalize_contracts(raw())
    return {}


def _schema_for_tool(
    tool_name: str,
    handler: object,
    contracts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    contract = contracts.get(tool_name)
    if contract is not None:
        schema = contract.get("inputSchema")
        if isinstance(schema, dict):
            return schema
    schema = function_to_schema(handler)
    if isinstance(schema, dict):
        return schema
    return {"type": "object", "properties": {}}


def _tool_description(tool: object, contract: dict[str, Any] | None) -> str:
    if contract:
        description = contract.get("description")
        if isinstance(description, str) and description:
            return description
    return getattr(tool, "description", None) or f"Call {getattr(tool, 'name', 'tool')}."


def direct_tool_registry(app: App, definition: StarDefinition, skill: Skill) -> ToolRegistry:
    """Compile a Star's canonical skill tools into an isolated MCP registry."""
    pending = tuple(skill._pending)
    names = tuple(tool.name for tool in pending)
    if definition.tools and names != definition.tools:
        msg = (
            f"Star {definition.name!r} manifest tools {definition.tools!r} "
            f"do not match skill tools {names!r}"
        )
        raise ValueError(msg)
    contracts = _load_contract_schemas(definition.python_package)
    return ToolRegistry(
        [
            ToolDef(
                name=tool.name,
                description=_tool_description(tool, contracts.get(tool.name)),
                handler=wrap_structured_mcp_handler(
                    tool.handler,
                    skill=skill.name,
                    tool=tool.name,
                ),
                schema=_schema_for_tool(tool.name, tool.handler, contracts),
                approval_required=tool.approval_required,
            )
            for tool in pending
        ],
        app.tool_events,
    )


def mount_direct_mcp(app: App, definition: StarDefinition, skill: Skill) -> ToolRegistry:
    """Mount a Star's direct MCP route and return its isolated registry."""
    registry = direct_tool_registry(app, definition, skill)

    async def direct_handler(request: Request) -> Response:
        return await handle_mcp_request(request, registry)

    direct_handler.__name__ = f"{definition.name.rsplit('/', 1)[-1].replace('-', '_')}_mcp"
    app.route(definition.direct_mcp_path, methods=["POST"], referenced=True)(direct_handler)
    return registry
