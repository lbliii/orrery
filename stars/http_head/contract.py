"""Stable contract for the bounded official HTTP metadata Star."""

from __future__ import annotations

from typing import Final

STAR_NAME: Final = "orrery/http-head"
STAR_VERSION: Final = "0.1.0"
DEFAULT_TARGET: Final = "python-3.14-whatsnew"

TARGETS: Final = {
    "python-3.14-whatsnew": "https://docs.python.org/3/whatsnew/3.14.html",
    "timeapi-utc": "https://timeapi.io/api/Time/current/zone?timeZone=UTC",
}

TOOL_SCHEMAS: Final = {
    "head": {
        "description": "Fetch fresh HTTP metadata for one allowlisted official target.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "enum": list(TARGETS),
                    "default": DEFAULT_TARGET,
                    "description": (
                        "Named allowlisted official target; arbitrary URLs are rejected."
                    ),
                }
            },
        },
    }
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
