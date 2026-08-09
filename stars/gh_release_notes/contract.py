from __future__ import annotations

from typing import Final

STAR_NAME: Final = "orrery/gh-release-notes"
STAR_VERSION: Final = "0.1.0"
DEFAULT_TARGET: Final = "flask"
TARGETS: Final = {
    "flask": ("pallets", "flask"),
    "mcp-python-sdk": ("modelcontextprotocol", "python-sdk"),
}
MAX_BYTES: Final = 512 * 1024
MAX_NOTES: Final = 4000
TOOL_SCHEMAS: Final = {
    "observe": {
        "description": "Observe latest release notes for a named allowlisted GitHub repository.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "enum": sorted(TARGETS), "default": DEFAULT_TARGET},
                "prior_body_digest": {"type": "string", "maxLength": 100},
            },
            "required": ["target"],
        },
    }
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
