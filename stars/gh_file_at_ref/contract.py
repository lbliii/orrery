from __future__ import annotations

from typing import Final

STAR_NAME: Final = "orrery/gh-file-at-ref"
STAR_VERSION: Final = "0.1.0"
DEFAULT_TARGET: Final = "orrery-readme"
TARGETS: Final = {
    "orrery-readme": ("lbliii", "orrery", "README.md"),
    "orrery-pyproject": ("lbliii", "orrery", "pyproject.toml"),
}
# Coverage ``check_param`` is ``target`` (same as the ``get`` tool schema).
MAX_BYTES: Final = 512 * 1024
MAX_TEXT_CHARS: Final = 4000
TOOL_SCHEMAS: Final = {
    "get": {
        "description": "Get a fixed GitHub file pinned to a full commit SHA.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "enum": sorted(TARGETS), "default": DEFAULT_TARGET},
                "ref": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
            },
            "required": ["target", "ref"],
        },
    }
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
