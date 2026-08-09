"""Production-safe Ed25519 identity loading for public direct Stars."""

from __future__ import annotations

import os
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

GLOBAL_PRIVATE_KEY_ENV = "ORRERY_STAR_PRIVATE_KEY"
GLOBAL_KEY_ID_ENV = "ORRERY_STAR_KEY_ID"


def public_star_signing_key(
    *, private_key: Any | None, private_key_env: str, key_id_env: str, default_key_id: str
) -> tuple[Ed25519PrivateKey, str]:
    """Prefer injected/per-Star identity, then the shared public-Star identity.

    Production refuses to mint an ephemeral key. Development/test may mint one
    only when no explicit key was configured.
    """
    if private_key is not None:
        return private_key, _key_id(key_id_env, default_key_id)
    per_star = os.environ.get(private_key_env, "").strip()
    global_key = os.environ.get(GLOBAL_PRIVATE_KEY_ENV, "").strip()
    if per_star:
        return _decode(per_star, private_key_env), _key_id(key_id_env, default_key_id)
    if global_key:
        key_id = os.environ.get(GLOBAL_KEY_ID_ENV, "").strip()
        if not key_id:
            if _production():
                raise RuntimeError(
                    f"{GLOBAL_KEY_ID_ENV} is required with {GLOBAL_PRIVATE_KEY_ENV} in production"
                )
            key_id = default_key_id
        return _decode(global_key, GLOBAL_PRIVATE_KEY_ENV), key_id
    if _production():
        raise RuntimeError(
            f"{private_key_env} or {GLOBAL_PRIVATE_KEY_ENV} is required in production"
        )
    return Ed25519PrivateKey.generate(), _key_id(key_id_env, default_key_id)


def _decode(raw: str, env_name: str) -> Ed25519PrivateKey:
    try:
        return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(raw))
    except ValueError as error:
        raise ValueError(f"{env_name} must be a hex Ed25519 private key") from error


def _key_id(env_name: str, default: str) -> str:
    value = os.environ.get(env_name, default).strip()
    if not value:
        raise ValueError(f"{env_name} must not be empty")
    return value


def _production() -> bool:
    return os.environ.get("CHIRP_ENV", "development").strip().lower() == "production"
