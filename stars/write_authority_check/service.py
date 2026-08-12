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

# Advisory fix text for agents — does not change authorized/codes semantics.
_REMEDIATION: dict[str, str] = {
    "manifest_digest_invalid": (
        "Pass a 64-character lowercase hex sha256 manifest digest from "
        "orrery/manifest-bind."
    ),
    "authority_invalid": (
        "Provide authority as an object with policy, allowed_paths, and grant_digest."
    ),
    "authority_unknown_fields": (
        "Remove unknown authority fields; only policy, allowed_paths, grant_digest, "
        "witness, and witness_public_key are allowed."
    ),
    "policy_invalid": (
        "Set authority.policy to a non-empty string within the max length."
    ),
    "policy_unknown": (
        "Use a known versioned policy (orrery/explicit-paths@v1)."
    ),
    "allowed_paths_invalid": (
        "Provide allowed_paths as a non-empty array of relative paths within limits."
    ),
    "path_invalid": (
        "Use relative paths matching [A-Za-z0-9._/-]+ without leading / or .. segments."
    ),
    "path_traversal": (
        "Remove path traversal segments (leading /, ../, or /../) from allowed_paths."
    ),
    "duplicate_path": (
        "Deduplicate allowed_paths so each path appears once."
    ),
    "grant_digest_invalid": (
        "Set grant_digest to a 64-character lowercase hex sha256 digest."
    ),
    "grant_digest_mismatch": (
        "Recompute grant_digest from canonical JSON of policy and sorted allowed_paths."
    ),
    "witness_public_key_without_witness": (
        "Supply a witness envelope when witness_public_key is set, or omit the key."
    ),
    "witness_invalid": (
        "Provide a valid Chirp Envelope wire object with all required fields."
    ),
    "witness_signature_invalid": (
        "Re-sign the witness envelope with the matching witness_public_key."
    ),
    "witness_missing_fields": (
        "Ensure witness payload includes grant_digest and allowed_paths."
    ),
    "witness_grant_digest_invalid": (
        "Set witness payload grant_digest to a 64-character lowercase hex sha256."
    ),
    "witness_grant_mismatch": (
        "Align witness payload grant_digest with the recomputed authority grant_digest."
    ),
    "witness_paths_invalid": (
        "Ensure witness payload allowed_paths is an array of path strings."
    ),
    "witness_paths_mismatch": (
        "Set witness payload allowed_paths to exactly match authority.allowed_paths."
    ),
    "witness_public_key_invalid": (
        "Provide witness_public_key as a 64-character lowercase hex Ed25519 public key."
    ),
}


def _error(code: str, **extra: object) -> dict[str, object]:
    item: dict[str, object] = {"error": code, "remediation": _REMEDIATION[code]}
    item.update(extra)
    return item


def _finding(code: str, message: str, **extra: object) -> dict[str, object]:
    item: dict[str, object] = {
        "code": code,
        "message": message,
        "remediation": _REMEDIATION[code],
    }
    item.update(extra)
    return item


def _findings_for_codes(codes: Sequence[str]) -> list[dict[str, object]]:
    return [_finding(code, _denial_message(code)) for code in codes]


def _denial_message(code: str) -> str:
    messages = {
        "grant_digest_mismatch": "claimed grant_digest does not match recomputed digest",
        "witness_public_key_without_witness": (
            "witness_public_key provided without a witness envelope"
        ),
        "witness_invalid": "witness envelope is invalid",
        "witness_signature_invalid": "witness envelope signature verification failed",
        "witness_missing_fields": "witness payload missing grant_digest or allowed_paths",
        "witness_grant_digest_invalid": "witness payload grant_digest is not valid hex",
        "witness_grant_mismatch": "witness payload grant_digest does not match authority",
        "witness_paths_invalid": "witness payload allowed_paths is invalid",
        "witness_paths_mismatch": "witness payload allowed_paths do not match authority",
        "witness_public_key_invalid": "witness_public_key is not valid hex",
    }
    return messages.get(code, code.replace("_", " "))


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
        return _error("manifest_digest_invalid")

    if not isinstance(authority, Mapping):
        return _error("authority_invalid")
    if set(authority) - {
        "policy",
        "allowed_paths",
        "grant_digest",
        "witness",
        "witness_public_key",
    }:
        return _error("authority_unknown_fields")

    policy = authority.get("policy")
    if not isinstance(policy, str) or not policy or len(policy) > MAX_POLICY_LEN:
        return _error("policy_invalid")
    if policy not in KNOWN_POLICIES:
        return _error("policy_unknown", policy=policy)

    paths_raw = authority.get("allowed_paths")
    if not isinstance(paths_raw, list) or not paths_raw or len(paths_raw) > MAX_PATHS:
        return _error("allowed_paths_invalid")

    allowed_paths: list[str] = []
    seen: set[str] = set()
    for index, path in enumerate(paths_raw):
        if not isinstance(path, str) or not path or len(path) > MAX_PATH_LEN:
            return _error("path_invalid", index=index)
        if path.startswith("/") or path.startswith("../") or "/../" in f"/{path}/":
            return _error("path_traversal", path=path, index=index)
        if not _PATH_RE.fullmatch(path):
            return _error("path_invalid", path=path, index=index)
        if path in seen:
            return _error("duplicate_path", path=path, index=index)
        seen.add(path)
        allowed_paths.append(path)

    claimed = authority.get("grant_digest")
    if not isinstance(claimed, str) or not _SHA256_RE.fullmatch(claimed):
        return _error("grant_digest_invalid")

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
    result: dict[str, object] = {
        "authorized": authorized,
        "codes": codes,
        "manifest_digest": manifest_digest,
        "policy": policy,
        "grant_digest": expected,
        "allowed_paths": sorted(allowed_paths),
        "witness_verified": witness_verified,
    }
    if codes:
        result["findings"] = _findings_for_codes(codes)
    return result


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
