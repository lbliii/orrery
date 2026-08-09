"""Shared durable signing-key configuration for managed CPU Star factories."""

from __future__ import annotations

import os
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

CPU_PRIVATE_KEY_ENV = "ORRERY_CPU_PRIVATE_KEY"
CPU_KEY_ID_ENV = "ORRERY_CPU_KEY_ID"
DEFAULT_CPU_KEY_ID = "orrery-cpu-1"


def cpu_signing_key(*, private_key: Any | None = None) -> tuple[Ed25519PrivateKey, str]:
    """Load the shared CPU signing identity; production never creates one."""
    if private_key is not None:
        return private_key, os.environ.get(CPU_KEY_ID_ENV, DEFAULT_CPU_KEY_ID)
    raw = os.environ.get(CPU_PRIVATE_KEY_ENV, "").strip()
    if raw:
        try:
            private = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(raw))
        except ValueError as error:
            raise ValueError(f"{CPU_PRIVATE_KEY_ENV} must be a hex Ed25519 private key") from error
    elif os.environ.get("CHIRP_ENV", "development").strip().lower() == "production":
        raise RuntimeError(f"{CPU_PRIVATE_KEY_ENV} is required in production")
    else:
        private = Ed25519PrivateKey.generate()
    key_id = os.environ.get(CPU_KEY_ID_ENV, DEFAULT_CPU_KEY_ID).strip()
    if not key_id:
        raise ValueError(f"{CPU_KEY_ID_ENV} must not be empty")
    return private, key_id
