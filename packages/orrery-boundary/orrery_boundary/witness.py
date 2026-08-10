"""``local/witness-approve`` — operator-signed write-authority witness (v1)."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Sequence
from typing import Any, Final

from chirp.skill import sign_envelope
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from orrery_boundary.grant import POLICY_EXPLICIT_PATHS, grant_digest

SKILL_NAME: Final = "orrery-boundary"
SKILL_VERSION: Final = "0.1.0"
TOOL_NAME: Final = "witness-approve"
MAX_PATHS: Final = 10_000
MAX_PATH_LEN: Final = 512
_PATH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
_HEX32_RE = re.compile(r"^[0-9a-f]{64}$")


def witness_approve(
    allowed_paths: Sequence[str],
    *,
    policy: str = POLICY_EXPLICIT_PATHS,
    private_key: Ed25519PrivateKey | bytes | None = None,
    key_id: str | None = None,
) -> dict[str, object]:
    """Emit a Chirp Envelope whose payload carries grant_digest + allowed_paths.

    Hosted ``orrery/write-authority-check`` verifies the wire object when the
    matching public key and authority record are supplied.
    """
    if not isinstance(policy, str) or not policy.strip():
        return {"error": "policy_invalid"}
    if policy != POLICY_EXPLICIT_PATHS:
        return {"error": "policy_unknown", "policy": policy}

    paths_or_error = _parse_paths(allowed_paths)
    if isinstance(paths_or_error, dict):
        return paths_or_error
    paths = paths_or_error

    key, resolved_key_id = _resolve_key(private_key=private_key, key_id=key_id)
    if key is None:
        return {"error": "witness_key_missing"}

    digest = grant_digest(policy, paths)
    payload = {"grant_digest": digest, "allowed_paths": list(paths)}
    arguments = {"allowed_paths": list(paths), "policy": policy}
    envelope = sign_envelope(
        payload=payload,
        skill=SKILL_NAME,
        version=SKILL_VERSION,
        tool=TOOL_NAME,
        input_digest=_input_digest(arguments),
        private_key=key,
        key_id=resolved_key_id,
    )
    public_hex = key.public_key().public_bytes_raw().hex()
    return {
        "witness": envelope.to_wire(),
        "witness_public_key": public_hex,
        "grant_digest": digest,
        "allowed_paths": sorted(str(path) for path in paths),
        "policy": policy,
        "key_id": resolved_key_id,
    }


def _parse_paths(allowed_paths: Sequence[str]) -> list[str] | dict[str, object]:
    if not isinstance(allowed_paths, list | tuple) or not allowed_paths:
        return {"error": "allowed_paths_invalid"}
    if len(allowed_paths) > MAX_PATHS:
        return {"error": "allowed_paths_too_many", "max_paths": MAX_PATHS}

    paths: list[str] = []
    seen: set[str] = set()
    for index, path in enumerate(allowed_paths):
        if not isinstance(path, str) or not path or len(path) > MAX_PATH_LEN:
            return {"error": "path_invalid", "index": index}
        if path.startswith("/") or path.startswith("../") or "/../" in f"/{path}/":
            return {"error": "path_traversal", "path": path, "index": index}
        if not _PATH_RE.fullmatch(path):
            return {"error": "path_invalid", "path": path, "index": index}
        if path in seen:
            return {"error": "duplicate_path", "path": path, "index": index}
        seen.add(path)
        paths.append(path)
    return paths


def _resolve_key(
    *,
    private_key: Ed25519PrivateKey | bytes | None,
    key_id: str | None,
) -> tuple[Ed25519PrivateKey | None, str]:
    resolved_id = (
        key_id
        or os.environ.get("ORRERY_BOUNDARY_WITNESS_KEY_ID")
        or "orrery-boundary-witness-1"
    )
    if private_key is not None:
        if isinstance(private_key, Ed25519PrivateKey):
            return private_key, resolved_id
        if isinstance(private_key, bytes | bytearray) and len(private_key) == 32:
            return Ed25519PrivateKey.from_private_bytes(bytes(private_key)), resolved_id
        return None, resolved_id

    env_hex = os.environ.get("ORRERY_BOUNDARY_WITNESS_PRIVATE_KEY", "").strip()
    if not env_hex or not _HEX32_RE.fullmatch(env_hex):
        return None, resolved_id
    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(env_hex)), resolved_id


def _input_digest(arguments: dict[str, Any]) -> str:
    canonical = json.dumps(
        arguments,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
