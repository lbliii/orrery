"""Direct, per-Star MCP endpoints backed by a canonical Star skill.

The aggregate host has one flat MCP tool namespace.  A Star's direct endpoint
does not: it exposes the package's natural tool names and uses the same Chirp
JSON-RPC handler as the host MCP surface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from chirp.http.request import Request
from chirp.http.response import Response
from chirp.skill import Skill
from chirp.tools.handler import handle_mcp_request
from chirp.tools.registry import ToolDef, ToolRegistry
from chirp.tools.schema import function_to_schema

from .definition import StarDefinition

if TYPE_CHECKING:
    from chirp import App


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
    return ToolRegistry(
        [
            ToolDef(
                name=tool.name,
                description=tool.description,
                handler=tool.handler,
                schema=function_to_schema(tool.handler),
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
