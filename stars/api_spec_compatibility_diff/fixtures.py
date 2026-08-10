"""Synthetic OpenAPI pairs for api-spec/compatibility-diff acceptance (#176)."""

from __future__ import annotations

import json
from typing import Final


def _entry(path: str, document: dict[str, object] | str) -> dict[str, str]:
    if isinstance(document, str):
        content = document
    else:
        content = json.dumps(document, indent=2, sort_keys=True) + "\n"
    return {"path": path, "content": content}


BASELINE_POLICY: Final = {
    "policy_id": "openapi-client-server-v1",
    "default_action": "report",
    "rules": [
        {
            "id": "breaking.path.remove",
            "severity": "breaking",
            "action": "block",
        },
        {
            "id": "info.description.change",
            "severity": "informational",
            "action": "allow",
        },
    ],
}

SOURCE_SPEC: Final = [
    _entry(
        "openapi.json",
        {
            "openapi": "3.0.3",
            "info": {
                "title": "Demo",
                "version": "1.0.0",
                "description": "baseline",
            },
            "paths": {
                "/pets": {
                    "get": {
                        "operationId": "listPets",
                        "responses": {"200": {"description": "ok"}},
                    }
                }
            },
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

# Known breaking: remove the only operation path.
BREAKING_TARGET: Final = [
    _entry(
        "openapi.json",
        {
            "openapi": "3.0.3",
            "info": {
                "title": "Demo",
                "version": "1.0.0",
                "description": "baseline",
            },
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

# Additive: new operation + schema.
ADDITIVE_TARGET: Final = [
    _entry(
        "openapi.json",
        {
            "openapi": "3.0.3",
            "info": {
                "title": "Demo",
                "version": "1.0.0",
                "description": "baseline",
            },
            "paths": {
                "/pets": {
                    "get": {
                        "operationId": "listPets",
                        "responses": {"200": {"description": "ok"}},
                    }
                },
                "/owners": {
                    "get": {
                        "operationId": "listOwners",
                        "responses": {"200": {"description": "ok"}},
                    }
                },
            },
            "components": {
                "schemas": {
                    "Pet": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                    },
                    "Owner": {
                        "type": "object",
                        "properties": {"id": {"type": "string"}},
                    },
                }
            },
        },
    )
]

# Policy-exempt informational description change under allow rule.
INFO_TARGET: Final = [
    _entry(
        "openapi.json",
        {
            "openapi": "3.0.3",
            "info": {
                "title": "Demo",
                "version": "1.0.0",
                "description": "updated docs only",
            },
            "paths": {
                "/pets": {
                    "get": {
                        "operationId": "listPets",
                        "responses": {"200": {"description": "ok"}},
                    }
                }
            },
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

# Ambiguous schema body change without an explicit policy rule.
AMBIGUOUS_TARGET: Final = [
    _entry(
        "openapi.json",
        {
            "openapi": "3.0.3",
            "info": {
                "title": "Demo",
                "version": "1.0.0",
                "description": "baseline",
            },
            "paths": {
                "/pets": {
                    "get": {
                        "operationId": "listPets",
                        "responses": {"200": {"description": "ok"}},
                    }
                }
            },
            "components": {
                "schemas": {
                    "Pet": {
                        "type": "object",
                        "required": ["name"],
                        "properties": {
                            "name": {"type": "integer"},
                        },
                    }
                }
            },
        },
    )
]
