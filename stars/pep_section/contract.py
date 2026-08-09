from __future__ import annotations

from typing import Final

STAR_NAME: Final = "orrery/pep-section"
STAR_VERSION: Final = "0.1.0"
PEP_SOURCES: Final = {
    "8": "https://peps.python.org/pep-0008/",
    "517": "https://peps.python.org/pep-0517/",
}
ALLOWED_SECTIONS: Final = {
    "8": frozenset({"Introduction", "Code Layout"}),
    "517": frozenset({"Build backend interface"}),
}
DEFAULT_PEP: Final = "8"
DEFAULT_SECTION: Final = "Introduction"
MAX_BYTES: Final = 512 * 1024
MAX_SLICE_CHARS: Final = 4_000
TOOL_SCHEMAS: Final = {
    "get": {
        "description": "Get a bounded named section from an allowlisted canonical Python PEP.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pep": {"type": "string", "enum": list(PEP_SOURCES), "default": DEFAULT_PEP},
                "section": {"type": "string", "default": DEFAULT_SECTION},
            },
            "required": ["pep", "section"],
        },
    }
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
