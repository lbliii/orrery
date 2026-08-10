from __future__ import annotations

from typing import Final

STAR_NAME: Final = "orrery/decision-bind"
STAR_VERSION: Final = "0.1.0"
MAX_DECISION_ID_LEN: Final = 128
MAX_STATEMENT_BYTES: Final = 16 * 1024

TOOL_SCHEMAS: Final = {
    "bind": {
        "description": (
            "Seal a planner decision statement into a citeable DecisionReceipt "
            "with a stable decision_digest."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "decision_id": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": MAX_DECISION_ID_LEN,
                },
                "statement": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": MAX_STATEMENT_BYTES,
                },
                "adr_url": {"type": "string", "format": "uri"},
                "issue_url": {"type": "string", "format": "uri"},
            },
            "required": ["decision_id", "statement"],
            "additionalProperties": False,
        },
    }
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
