"""Synthetic OpenAPI documents for api-spec/openapi-inventory acceptance (#174)."""

from __future__ import annotations

import json
from typing import Final


def _entry(path: str, document: dict[str, object] | str) -> dict[str, str]:
    if isinstance(document, str):
        content = document
    else:
        content = json.dumps(document, indent=2, sort_keys=True) + "\n"
    return {"path": path, "content": content}


BASELINE_SPEC: Final = [
    _entry(
        "openapi.json",
        {
            "openapi": "3.0.3",
            "info": {"title": "Demo", "version": "1.0.0"},
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
                        "nullable": True,
                        "properties": {
                            "name": {"type": "string", "format": "byte", "example": "fido"},
                            "kind": {"$ref": "#/components/schemas/Kind"},
                        },
                        "discriminator": {
                            "propertyName": "kind",
                            "mapping": {"dog": "#/components/schemas/Pet"},
                        },
                        "x-internal-id": "pet-1",
                    },
                    "Kind": {"type": "string"},
                },
                "securitySchemes": {
                    "bearer": {"type": "http", "scheme": "bearer"},
                },
            },
            "webhooks": {
                "newPet": {
                    "post": {
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Pet"}
                                }
                            }
                        },
                        "responses": {"200": {"description": "ok"}},
                    }
                }
            },
        },
    )
]

EXTERNAL_REF_SPEC: Final = [
    _entry(
        "openapi.json",
        {
            "openapi": "3.0.3",
            "info": {"title": "External", "version": "1.0.0"},
            "paths": {},
            "components": {
                "schemas": {
                    "Remote": {"$ref": "https://example.com/schemas/remote.json"}
                }
            },
        },
    )
]

MALFORMED_SPEC: Final = [
    _entry("openapi.json", '{"openapi": "3.0.3", "info": '),
]

COMPATIBLE_MINIMAL: Final = [
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
