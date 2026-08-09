from __future__ import annotations

from typing import Final

STAR_NAME: Final = "orrery/cert-expiry"
STAR_VERSION: Final = "0.1.0"
DEFAULT_HOST: Final = "orrery-public"
HOSTS: Final = {"orrery-public": "orrery.lol", "python-docs": "docs.python.org"}

TOOL_SCHEMAS: Final = {
    "inspect": {
        "description": "Inspect TLS certificate expiry for a named allowlisted HTTPS host.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "enum": list(HOSTS), "default": DEFAULT_HOST}
            },
        },
    }
}


def tool_schemas() -> dict[str, object]:
    import copy

    return copy.deepcopy(TOOL_SCHEMAS)
