from __future__ import annotations

from typing import Final, Literal

FeatureClass = Literal[
    "safe",
    "transformable",
    "decision_required",
    "unsupported",
    "malformed",
]

RefPolicyMode = Literal["deny_external", "allow_prefixes"]

STAR_NAME: Final = "orrery/api-spec-openapi-inventory"
STAR_VERSION: Final = "0.1.0"
MAX_ENTRIES: Final = 256
MAX_ENTRY_BYTES: Final = 256 * 1024
MAX_FINDINGS: Final = 4096
MAX_MESSAGE_BYTES: Final = 512
MAX_WALK_NODES: Final = 50_000

FEATURE_CLASSES: Final = frozenset(
    {"safe", "transformable", "decision_required", "unsupported", "malformed"}
)

REF_POLICY_MODES: Final = frozenset({"deny_external", "allow_prefixes"})

TOOL_SCHEMAS: Final = {
    "inventory": {
        "description": (
            "Parse bounded OpenAPI document entries and emit a deterministic "
            "inventory with classified findings, dialect/version, and stable digests. "
            "Does not fetch external $ref targets or claim semantic upgrade."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "entries": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": MAX_ENTRIES,
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "minLength": 1},
                            "content": {"type": "string"},
                        },
                        "required": ["path", "content"],
                        "additionalProperties": False,
                    },
                },
                "ref_policy": {
                    "type": "object",
                    "properties": {
                        "mode": {
                            "type": "string",
                            "enum": sorted(REF_POLICY_MODES),
                        },
                        "allowed_prefixes": {
                            "type": "array",
                            "items": {"type": "string", "minLength": 1},
                            "maxItems": 64,
                        },
                    },
                    "required": ["mode"],
                    "additionalProperties": False,
                },
            },
            "required": ["entries"],
            "additionalProperties": False,
        },
    }
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
