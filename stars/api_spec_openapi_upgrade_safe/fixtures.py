"""Synthetic OpenAPI trees for api-spec/openapi-upgrade-safe acceptance (#175)."""

from __future__ import annotations

import json
from typing import Final


def _entry(path: str, document: dict[str, object] | str) -> dict[str, str]:
    if isinstance(document, str):
        content = document
    else:
        content = json.dumps(document, indent=2, sort_keys=True) + "\n"
    return {"path": path, "content": content}


# Corpus-backed safe subset: draft bump + nullable conversion only.
SAFE_SPEC: Final = [
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
                            "name": {"type": "string", "format": "byte"},
                        },
                    }
                }
            },
        },
    )
]

# Unsupported semantic construct must surface — never silently equivalent.
UNSUPPORTED_SPEC: Final = [
    _entry(
        "openapi.json",
        {
            "openapi": "3.0.3",
            "info": {"title": "Disc", "version": "1.0.0"},
            "paths": {},
            "components": {
                "schemas": {
                    "Animal": {
                        "type": "object",
                        "discriminator": {
                            "propertyName": "kind",
                            "mapping": {"cat": "#/components/schemas/Cat"},
                        },
                    }
                }
            },
        },
    )
]

# Vendor extensions require an explicit policy decision.
EXTENSION_SPEC: Final = [
    _entry(
        "openapi.json",
        {
            "openapi": "3.0.3",
            "info": {"title": "Ext", "version": "1.0.0"},
            "paths": {},
            "components": {
                "schemas": {
                    "Pet": {
                        "type": "object",
                        "x-internal-id": "pet-1",
                        "properties": {"name": {"type": "string"}},
                    }
                }
            },
        },
    )
]

MALFORMED_SPEC: Final = [
    _entry("openapi.json", '{"openapi": "3.0.3", "info": '),
]
