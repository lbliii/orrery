"""Synthetic OpenAPI targets for api-spec/openapi-validate acceptance (#177)."""

from __future__ import annotations

import json
from typing import Final


def _entry(path: str, document: dict[str, object] | str) -> dict[str, str]:
    if isinstance(document, str):
        content = document
    else:
        content = json.dumps(document, indent=2, sort_keys=True) + "\n"
    return {"path": path, "content": content}


MALFORMED_TARGET: Final = [
    _entry("openapi.json", '{"openapi": "3.0.3", "info": ')
]

SAFE_SOURCE: Final = [
    _entry(
        "openapi.json",
        {
            "openapi": "3.0.3",
            "info": {"title": "Demo", "version": "1.0.0"},
            "paths": {},
            "components": {
                "schemas": {
                    "Pet": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                    }
                }
            },
        },
    )
]

POLICY_BLOCK_PLAN: Final = {
    "analysis_digest": "b" * 64,
    "profile_digest": "3" * 64,
    "compatibility_policy": {"policy_id": "openapi-client-server-v1"},
    "planned_ops": [
        {
            "op": "remove_path",
            "path": "/gone",
            "severity": "breaking",
        }
    ],
    "plan_digest": "a" * 64,
}

VALID_TARGET: Final = [
    _entry(
        "openapi.json",
        {
            "openapi": "3.1.0",
            "info": {"title": "Demo", "version": "1.0.0"},
            "paths": {},
            "components": {
                "schemas": {
                    "Pet": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                    }
                }
            },
        },
    )
]
