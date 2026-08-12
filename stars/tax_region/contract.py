"""Stable contract for offline tax-jurisdiction shape validation."""

from __future__ import annotations

from typing import Final

STAR_NAME: Final = "orrery/tax-region"
STAR_VERSION: Final = "0.1.0"
DEFAULT_PROFILE: Final = "sales-jurisdiction"
MAX_ERRORS: Final = 10
PROFILES: Final = {
    DEFAULT_PROFILE: {
        "version": "1",
        "fields": {
            "country": {
                "type": "string",
                "pattern": "^[A-Z]{2}$",
                "description": "ISO 3166-1 alpha-2 country code.",
            },
            "region": {
                "type": "string",
                "pattern": "^[A-Z]{2}$",
                "description": "Uppercase subdivision code (state/province).",
            },
            "jurisdiction_key": {
                "type": "string",
                "pattern": "^[A-Z]{2}-[A-Z]{2}$",
                "description": "Composite jurisdiction identifier (country-region).",
            },
        },
    }
}
JURISDICTION_SCHEMA: Final = {
    "type": "object",
    "properties": PROFILES[DEFAULT_PROFILE]["fields"],
    "required": ["country", "region", "jurisdiction_key"],
    "additionalProperties": False,
}
TOOL_SCHEMAS: Final = {
    "validate": {
        "description": (
            "Validate one small tax-jurisdiction record against a named static profile."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "profile": {
                    "type": "string",
                    "enum": [DEFAULT_PROFILE],
                    "default": DEFAULT_PROFILE,
                },
                "jurisdiction": JURISDICTION_SCHEMA,
            },
            "required": ["profile", "jurisdiction"],
            "additionalProperties": False,
        },
    }
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
