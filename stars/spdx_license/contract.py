from __future__ import annotations

from typing import Final

STAR_NAME: Final = "orrery/spdx-license"
STAR_VERSION: Final = "0.1.0"
LICENSE_IDS: Final = frozenset({"Apache-2.0", "BSD-3-Clause", "MIT", "MPL-2.0"})
DEFAULT_LICENSE_ID: Final = "MIT"
MAX_BYTES: Final = 512 * 1024
MAX_TEXT_CHARS: Final = 4_000
MAX_SEE_ALSO: Final = 5
MAX_SEE_ALSO_CHARS: Final = 512

TOOL_SCHEMAS: Final = {
    "get": {
        "description": "Get bounded metadata and license text for a named allowlisted SPDX ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "license_id": {
                    "type": "string",
                    "enum": sorted(LICENSE_IDS),
                    "default": DEFAULT_LICENSE_ID,
                },
            },
            "required": ["license_id"],
        },
    }
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
