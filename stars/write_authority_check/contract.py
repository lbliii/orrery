from __future__ import annotations

from typing import Final

STAR_NAME: Final = "orrery/write-authority-check"
STAR_VERSION: Final = "0.1.0"
MAX_PATHS: Final = 10_000
MAX_PATH_LEN: Final = 512
MAX_POLICY_LEN: Final = 128
SHA256_HEX_LEN: Final = 64
ED25519_PUBLIC_HEX_LEN: Final = 64

POLICY_EXPLICIT_PATHS: Final = "orrery/explicit-paths@v1"
KNOWN_POLICIES: Final = frozenset({POLICY_EXPLICIT_PATHS})

AUTHORITY_SCHEMA: Final = {
    "type": "object",
    "properties": {
        "policy": {"type": "string", "minLength": 1, "maxLength": MAX_POLICY_LEN},
        "allowed_paths": {
            "type": "array",
            "minItems": 1,
            "maxItems": MAX_PATHS,
            "items": {"type": "string", "minLength": 1, "maxLength": MAX_PATH_LEN},
        },
        "grant_digest": {
            "type": "string",
            "minLength": SHA256_HEX_LEN,
            "maxLength": SHA256_HEX_LEN,
        },
        "witness": {"type": "object"},
        "witness_public_key": {
            "type": "string",
            "minLength": ED25519_PUBLIC_HEX_LEN,
            "maxLength": ED25519_PUBLIC_HEX_LEN,
        },
    },
    "required": ["policy", "allowed_paths", "grant_digest"],
    "additionalProperties": False,
}

TOOL_SCHEMAS: Final = {
    "check": {
        "description": (
            "Verify an explicit write grant covers the intended path set "
            "(optional signed witness envelope)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "manifest_digest": {
                    "type": "string",
                    "minLength": SHA256_HEX_LEN,
                    "maxLength": SHA256_HEX_LEN,
                },
                "authority": AUTHORITY_SCHEMA,
            },
            "required": ["manifest_digest", "authority"],
            "additionalProperties": False,
        },
    }
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
