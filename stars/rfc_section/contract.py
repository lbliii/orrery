from __future__ import annotations

from typing import Final

STAR_NAME: Final = "orrery/rfc-section"
STAR_VERSION: Final = "0.1.0"
RFC_SOURCES: Final = {
    "9110": "https://www.rfc-editor.org/rfc/rfc9110.txt",
    "9111": "https://www.rfc-editor.org/rfc/rfc9111.txt",
}
ALLOWED_SECTIONS: Final = {"9110": frozenset({"3.1", "4"}), "9111": frozenset({"4"})}
DEFAULT_RFC: Final = "9110"
DEFAULT_SECTION: Final = "3.1"
MAX_BYTES: Final = 512 * 1024
MAX_SLICE_CHARS: Final = 4_000

TOOL_SCHEMAS: Final = {
    "get": {
        "description": "Get a bounded named section from an allowlisted RFC Editor document.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "rfc": {"type": "string", "enum": list(RFC_SOURCES), "default": DEFAULT_RFC},
                "section": {"type": "string", "default": DEFAULT_SECTION},
            },
            "required": ["rfc", "section"],
        },
    }
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
