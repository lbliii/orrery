from __future__ import annotations

from typing import Final

STAR_NAME: Final = "orrery/acceptance-bind"
STAR_VERSION: Final = "0.1.0"
MAX_ACCEPTANCE_ID_LEN: Final = 128
MAX_CRITERIA: Final = 32
MAX_CRITERION_ID_LEN: Final = 64
MAX_STATEMENT_BYTES: Final = 4 * 1024
MAX_VERIFY_REF_LEN: Final = 1024
MAX_VERIFY_EXPECT_LEN: Final = 1024

VERIFY_KINDS: Final = frozenset(
    {
        "pytest",
        "command",
        "http_smoke",
        "envelope_verify",
        "digest_eq",
        "external_ref",
    }
)

VERIFY_REF_SCHEMA: Final = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": sorted(VERIFY_KINDS)},
        "ref": {"type": "string", "minLength": 1, "maxLength": MAX_VERIFY_REF_LEN},
        "expect": {"type": "string", "maxLength": MAX_VERIFY_EXPECT_LEN},
    },
    "required": ["kind", "ref"],
    "additionalProperties": False,
}

CRITERION_SCHEMA: Final = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "minLength": 1, "maxLength": MAX_CRITERION_ID_LEN},
        "statement": {"type": "string", "minLength": 1, "maxLength": MAX_STATEMENT_BYTES},
        "verify": VERIFY_REF_SCHEMA,
    },
    "required": ["id", "statement", "verify"],
    "additionalProperties": False,
}

TOOL_SCHEMAS: Final = {
    "bind": {
        "description": (
            "Seal sprint done-criteria plus VerifyRef pointers into a citeable "
            "AcceptanceReceipt with a stable acceptance_digest."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "acceptance_id": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": MAX_ACCEPTANCE_ID_LEN,
                },
                "criteria": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": MAX_CRITERIA,
                    "items": CRITERION_SCHEMA,
                },
                "adr_url": {"type": "string", "format": "uri"},
                "issue_url": {"type": "string", "format": "uri"},
            },
            "required": ["acceptance_id", "criteria"],
            "additionalProperties": False,
        },
    }
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
