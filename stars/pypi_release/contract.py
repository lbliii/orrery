from __future__ import annotations

from typing import Final

STAR_NAME: Final = "orrery/pypi-release"
STAR_VERSION: Final = "0.1.0"
DEFAULT_PACKAGE: Final = "httpx"
PACKAGES: Final = frozenset({"httpx", "pydantic"})
MAX_BYTES: Final = 1024 * 1024
MAX_FILES: Final = 10
TOOL_SCHEMAS: Final = {
    "get": {
        "description": "Get current release metadata for a named allowlisted PyPI package.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "package": {"type": "string", "enum": sorted(PACKAGES), "default": DEFAULT_PACKAGE}
            },
            "required": ["package"],
        },
    }
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
