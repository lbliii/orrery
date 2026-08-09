"""Public Ed25519 key-set projection for portable Envelope verification."""

from __future__ import annotations

import base64
from collections.abc import Mapping
from typing import Any

KEY_SET_PATH = "/.well-known/orrery/keys.json"
KEY_SET_CACHE_CONTROL = "public, max-age=3600, stale-while-revalidate=300"


def key_set_url(origin: str) -> str:
    return f"{origin.rstrip('/')}{KEY_SET_PATH}"


def public_key_set(skills: Mapping[str, Any], *, origin: str) -> dict[str, object]:
    """Emit an immutable-key JWKS-like document from mounted direct Star skills."""
    keys = []
    for name, skill in sorted(skills.items()):
        public = skill.public_key
        if public is None:
            continue
        keys.append(
            {
                "kty": "OKP",
                "crv": "Ed25519",
                "x": base64.urlsafe_b64encode(public).rstrip(b"=").decode("ascii"),
                "kid": str(skill.key_id),
                "alg": "EdDSA",
                "use": "sig",
                "star": name,
                "envelope_alg": "Ed25519",
            }
        )
    return {
        "keys": keys,
        "key_set_url": key_set_url(origin),
        "rotation": {
            "strategy": "publish new kid before signing with it; retain prior keys until all "
            "Envelope verification windows have elapsed",
            "cache_control": KEY_SET_CACHE_CONTROL,
        },
    }
