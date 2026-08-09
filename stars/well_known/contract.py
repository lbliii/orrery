from __future__ import annotations

from typing import Final

STAR_NAME: Final = "orrery/well-known"
STAR_VERSION: Final = "0.1.0"
DEFAULT_DOCUMENT: Final = "orrery-llms"
DOCUMENTS: Final = {
    "orrery-llms": ("https://orrery.lol/llms.txt", "text"),
    "orrery-mcp-server-card": ("https://orrery.lol/.well-known/mcp/server-card.json", "mcp-card"),
}
MAX_BYTES: Final = 64 * 1024
MAX_SLICE_CHARS: Final = 2_000

TOOL_SCHEMAS: Final = {
    "read": {
        "description": "Read a bounded slice from a named allowlisted well-known document.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "document": {"type": "string", "enum": list(DOCUMENTS), "default": DEFAULT_DOCUMENT}
            },
        },
    }
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
