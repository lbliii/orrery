from __future__ import annotations

from typing import Final

STAR_NAME: Final = "orrery/npm-release"
STAR_VERSION: Final = "0.1.0"
DEFAULT_PACKAGE: Final = "zod"
PACKAGE_PATHS: Final = {
    "zod": "zod/latest",
    "@modelcontextprotocol/sdk": "%40modelcontextprotocol%2Fsdk/latest",
}
MAX_BYTES: Final = 512 * 1024
MAX_DEPENDENCIES: Final = 25
TOOL_SCHEMAS: Final = {
    "get": {
        "description": "Get latest dist-tag metadata for a named allowlisted npm package.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "package": {
                    "type": "string",
                    "enum": sorted(PACKAGE_PATHS),
                    "default": DEFAULT_PACKAGE,
                }
            },
            "required": ["package"],
        },
    }
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
