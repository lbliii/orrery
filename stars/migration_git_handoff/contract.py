from __future__ import annotations

from typing import Final

STAR_NAME: Final = "orrery/migration-git-handoff"
STAR_VERSION: Final = "0.1.0"
HANDOFF_RECEIPT_SCHEMA_VERSION: Final = "migration-git-handoff/v1"

SHA256_HEX_LEN: Final = 64
MAX_PATH_LEN: Final = 512
MAX_ROOTS: Final = 64
MAX_POLICY_LEN: Final = 128
MAX_BRANCH_LEN: Final = 256
MAX_PR_REF_LEN: Final = 256

POLICY_CHECKOUT_ROOTS: Final = "orrery/checkout-roots@v1"
POLICY_MIGRATION_HANDOFF: Final = "orrery/migration-handoff@v1"
KNOWN_REPO_POLICIES: Final = frozenset({POLICY_CHECKOUT_ROOTS})
KNOWN_AUTHORITY_POLICIES: Final = frozenset({POLICY_MIGRATION_HANDOFF})

PRIVATE_RECEIPT_KEYS: Final = frozenset(
    {
        "token",
        "github_token",
        "repo_token",
        "source_bytes",
        "target_bytes",
        "patch_text",
        "full_patch_text",
        "source_content",
        "target_content",
        "patch",
        "diff",
        "raw_source",
        "source_text",
    }
)

TOOL_SCHEMAS: Final = {
    "handoff": {
        "description": (
            "Verify a sealed migration bundle and emit a digest-only Git/PR handoff "
            "receipt (no repo credentials or source bodies)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "profile": {"type": "object"},
                "change_bundle": {"type": "object"},
                "repo_identity_policy": {"type": "object"},
                "checkout_root": {"type": "string", "minLength": 1, "maxLength": MAX_PATH_LEN},
                "authority": {"type": "object"},
                "local_validation": {"type": "object"},
                "branch_or_pr_ref": {"type": "object"},
                "sealed_validation_digest": {
                    "type": "string",
                    "minLength": SHA256_HEX_LEN,
                    "maxLength": SHA256_HEX_LEN,
                },
                "composite_receipt_digest": {
                    "type": "string",
                    "minLength": SHA256_HEX_LEN,
                    "maxLength": SHA256_HEX_LEN,
                },
            },
            "required": [
                "profile",
                "change_bundle",
                "repo_identity_policy",
                "checkout_root",
                "authority",
                "local_validation",
                "branch_or_pr_ref",
            ],
            "additionalProperties": False,
        },
    }
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
