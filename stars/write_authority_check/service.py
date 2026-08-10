"""Pure write-authority check over caller digests and optional witness envelopes."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence

from chirp.skill import Envelope, verify_envelope

from .contract import (
    ED25519_PUBLIC_HEX_LEN,
    KNOWN_POLICIES,
    MAX_PATH_LEN,
    MAX_PATHS,
    MAX_POLICY_LEN,
    SHA256_HEX_LEN,
)

_SHA256_RE = re.compile(rf"^[0-9a-f]{{{SHA256_HEX_LEN}}}$")
_PATH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
_HEX_KEY_RE = re.compile(rf"^[0-9a-f]{{{ED25519_PUBLIC_HEX_LEN}}}$")

_ENVELOPE_FIELDS = (
    "payload",
    "skill",
    "version",
    "tool",
    "nonce",
    "input_digest",
    "signature",
    "key_id",
    "alg",
)


def grant_digest(policy: str, allowed_paths: Sequence[str]) -> str:
    """Lowercase hex sha256 over canonical ``{policy, allowed_paths}``."""
    payload = {
        "allowed_paths": sorted(str(path) for path in allowed_paths),
        "policy": policy,
    }
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(body.encode()).hexdigest()


def check(manifest_digest: object, authority: object) -> dict[str, object]:
    """Authorize or deny a write grant; optional witness must verify and cover paths."""
    if (
        not isinstance(manifest_digest, str)
        or not _SHA256_RE.fullmatch(manifest_digest)
    ):
        return {"error": "manifest_digest_invalid"}

    if not isinstance(authority, Mapping):
        return {"error": "authority_invalid"}
    if set(authority) - {
        "policy",
        "allowed_paths",
        "grant_digest",
        "witness",
        "witness_public_key",
    }:
        return {"error": "authority_unknown_fields"}

    policy = authority.get("policy")
    if not isinstance(policy, str) or not policy or len(policy) > MAX_POLICY_LEN:
        return {"error": "policy_invalid"}
    if policy not in KNOWN_POLICIES:
        return {"error": "policy_unknown", "policy": policy}

    paths_raw = authority.get("allowed_paths")
    if not isinstance(paths_raw, list) or not paths_raw or len(paths_raw) > MAX_PATHS:
        return {"error": "allowed_paths_invalid"}

    allowed_paths: list[str] = []
    seen: set[str] = set()
    for index, path in enumerate(paths_raw):
        if not isinstance(path, str) or not path or len(path) > MAX_PATH_LEN:
            return {"error": "path_invalid", "index": index}
        if path.startswith("/") or path.startswith("../") or "/../" in f"/{path}/":
            return {"error": "path_traversal", "path": path, "index": index}
        if not _PATH_RE.fullmatch(path):
            return {"error": "path_invalid", "path": path, "index": index}
        if path in seen:
            return {"error": "duplicate_path", "path": path, "index": index}
        seen.add(path)
        allowed_paths.append(path)

    claimed = authority.get("grant_digest")
    if not isinstance(claimed, str) or not _SHA256_RE.fullmatch(claimed):
        return {"error": "grant_digest_invalid"}

    expected = grant_digest(policy, allowed_paths)
    codes: list[str] = []
    if claimed != expected:
        codes.append("grant_digest_mismatch")

    witness = authority.get("witness")
    if witness is not None:
        witness_codes = _verify_witness(
            witness,
            authority.get("witness_public_key"),
            expected_grant=expected,
            allowed_paths=allowed_paths,
        )
        codes.extend(witness_codes)
    elif "witness_public_key" in authority:
        codes.append("witness_public_key_without_witness")

    authorized = not codes
    witness_fail_codes = {
        "witness_invalid",
        "witness_signature_invalid",
        "witness_public_key_invalid",
        "witness_missing_fields",
        "witness_grant_digest_invalid",
        "witness_grant_mismatch",
        "witness_paths_invalid",
        "witness_paths_mismatch",
        "witness_public_key_without_witness",
    }
    witness_verified = (
        witness is not None and authorized and not (set(codes) & witness_fail_codes)
    )
    return {
        "authorized": authorized,
        "codes": codes,
        "manifest_digest": manifest_digest,
        "policy": policy,
        "grant_digest": expected,
        "allowed_paths": sorted(allowed_paths),
        "witness_verified": witness_verified,
    }


def _verify_witness(
    witness: object,
    public_key_hex: object,
    *,
    expected_grant: str,
    allowed_paths: Sequence[str],
) -> list[str]:
    if not isinstance(witness, Mapping):
        return ["witness_invalid"]
    if not isinstance(public_key_hex, str) or not _HEX_KEY_RE.fullmatch(public_key_hex):
        return ["witness_public_key_invalid"]

    missing = [field for field in _ENVELOPE_FIELDS if field not in witness]
    if missing:
        return ["witness_invalid"]

    try:
        envelope = Envelope(
            payload=witness["payload"],
            skill=str(witness["skill"]),
            version=str(witness["version"]),
            tool=str(witness["tool"]),
            nonce=str(witness["nonce"]),
            input_digest=str(witness["input_digest"]),
            signature=str(witness["signature"]),
            key_id=str(witness["key_id"]),
            alg=str(witness.get("alg", "Ed25519")),
        )
        public_key = bytes.fromhex(public_key_hex)
    except (KeyError, TypeError, ValueError):
        return ["witness_invalid"]

    if not verify_envelope(envelope, public_key):
        return ["witness_signature_invalid"]

    payload = envelope.payload
    if not isinstance(payload, Mapping):
        return ["witness_missing_fields"]

    codes: list[str] = []
    witness_grant = payload.get("grant_digest")
    witness_paths = payload.get("allowed_paths")
    if not isinstance(witness_grant, str) or not isinstance(witness_paths, list):
        return ["witness_missing_fields"]
    if not _SHA256_RE.fullmatch(witness_grant):
        codes.append("witness_grant_digest_invalid")
    elif witness_grant != expected_grant:
        codes.append("witness_grant_mismatch")

    if any(not isinstance(path, str) for path in witness_paths):
        codes.append("witness_paths_invalid")
    else:
        witness_set = set(witness_paths)
        needed = set(allowed_paths)
        if witness_set != needed:
            # Exact cover: grant must match the path set under check.
            codes.append("witness_paths_mismatch")

    return codes
