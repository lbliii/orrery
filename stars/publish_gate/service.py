"""Publish-gate composition (#216).

Frozen planner subgraph: prior artifact envelope → publish-profile
write-authority-check → optional human witness → in-package release seal.
v1 does not perform git push / pages deploy (authority seam + seal only).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping

from chirp.skill import Envelope, verify_envelope

from stars.write_authority_check.service import check as write_authority_check

CONSTELLATION = "orrery/publish-gate"
DISPOSITIONS = ("released", "denied", "awaiting_witness", "inconclusive")
PROFILE_PUBLISH = "publish"
_PRIOR_CONSTELLATION = "orrery/authorized-content-patch"
_PRIOR_DISPOSITION = "authorized"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_HEX_KEY_RE = re.compile(r"^[0-9a-f]{64}$")
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
_COMPONENTS = (
    {"name": "orrery/write-authority-check", "version": "0.1.0"},
)
_LIMITATIONS = (
    "Authority seam + release seal only — no git push / pages deploy.",
    "Two-phase model: edit via orrery/authorized-content-patch, then publish-gate.",
    "Publish authority profile is distinct from edit (authority.profile=publish).",
    "awaiting_witness only when pause_policy.allowed (ADR 0007); resume MCP out of scope.",
    "Composite seal is in-package (no orrery/artifact-seal star).",
    "Prior signature verify runs only when prior_public_key is supplied.",
)


def run(
    prior_envelope: object,
    authority: object,
    *,
    prior_public_key: object | None = None,
    require_witness: object = False,
) -> dict[str, object]:
    """Run the frozen publish-gate subgraph and seal a disposition.

    Caller supplies a prior edit-phase artifact envelope plus a publish-profile
    write grant. Orrery never pushes git or deploys pages.
    """
    prior, prior_error = _assess_prior(prior_envelope, prior_public_key)
    if prior_error is not None:
        return _seal(disposition="inconclusive", stages={"prior-artifact": prior_error})

    assert prior is not None
    stages: dict[str, object] = {"prior-artifact": prior}

    if not isinstance(require_witness, bool):
        return _seal(
            disposition="inconclusive",
            stages={
                **stages,
                "human-witness": {"error": "require_witness_invalid"},
            },
        )

    publish_authority, profile_error = _publish_authority(authority)
    if profile_error is not None:
        return _seal(
            disposition="inconclusive",
            stages={**stages, "write-authority-check": profile_error},
        )

    assert publish_authority is not None
    manifest_digest = prior.get("manifest_digest")
    if not isinstance(manifest_digest, str) or not _SHA256_RE.fullmatch(manifest_digest):
        return _seal(
            disposition="inconclusive",
            stages={
                **stages,
                "write-authority-check": {"error": "manifest_digest_missing"},
            },
        )

    # Grant check first (paths / digest). Witness handled in the next stage so
    # the graph can pause at human-witness without re-deciding pause_policy.
    grant_authority = {
        key: value
        for key, value in publish_authority.items()
        if key not in {"witness", "witness_public_key"}
    }
    authority_result = write_authority_check(manifest_digest, grant_authority)
    stages["write-authority-check"] = authority_result
    if "error" in authority_result:
        return _seal(disposition="inconclusive", stages=stages)
    if not bool(authority_result.get("authorized")):
        return _seal(disposition="denied", stages=stages)

    witness_stage = _assess_witness(
        publish_authority,
        manifest_digest=manifest_digest,
        require_witness=require_witness,
    )
    stages["human-witness"] = witness_stage
    if witness_stage.get("status") == "awaiting":
        return _seal(disposition="awaiting_witness", stages=stages)
    if witness_stage.get("status") in {"invalid", "error"}:
        return _seal(disposition="denied", stages=stages)

    return _seal(disposition="released", stages=stages)


def _assess_prior(
    prior_envelope: object,
    prior_public_key: object | None,
) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    if not isinstance(prior_envelope, Mapping):
        return None, {"error": "prior_envelope_invalid"}
    # ``alg`` may be omitted (Chirp defaults to Ed25519).
    required = [field for field in _ENVELOPE_FIELDS if field != "alg"]
    missing = [field for field in required if field not in prior_envelope]
    if missing:
        return None, {"error": "prior_envelope_missing_fields", "fields": missing}

    payload = prior_envelope.get("payload")
    if not isinstance(payload, Mapping):
        return None, {"error": "prior_payload_invalid"}

    disposition = payload.get("disposition")
    if disposition != _PRIOR_DISPOSITION:
        return None, {
            "error": "prior_disposition_invalid",
            "disposition": disposition,
            "expected": _PRIOR_DISPOSITION,
        }

    constellation = payload.get("constellation")
    if constellation != _PRIOR_CONSTELLATION:
        return None, {
            "error": "prior_constellation_invalid",
            "constellation": constellation,
            "expected": _PRIOR_CONSTELLATION,
        }

    if prior_public_key is not None:
        verify_error = _verify_prior_signature(prior_envelope, prior_public_key)
        if verify_error is not None:
            return None, verify_error

    stages = payload.get("stages")
    manifest_digest = None
    if isinstance(stages, Mapping):
        bound = stages.get("manifest-bind")
        if isinstance(bound, Mapping):
            digest = bound.get("manifest_digest")
            if isinstance(digest, str):
                manifest_digest = digest

    return {
        "valid": True,
        "constellation": constellation,
        "disposition": disposition,
        "manifest_digest": manifest_digest,
        "signature_verified": prior_public_key is not None,
        "skill": prior_envelope.get("skill"),
        "tool": prior_envelope.get("tool"),
    }, None


def _verify_prior_signature(
    prior_envelope: Mapping[str, object],
    prior_public_key: object,
) -> dict[str, object] | None:
    if not isinstance(prior_public_key, str) or not _HEX_KEY_RE.fullmatch(
        prior_public_key
    ):
        return {"error": "prior_public_key_invalid"}
    try:
        envelope = Envelope(
            payload=prior_envelope["payload"],
            skill=str(prior_envelope["skill"]),
            version=str(prior_envelope["version"]),
            tool=str(prior_envelope["tool"]),
            nonce=str(prior_envelope["nonce"]),
            input_digest=str(prior_envelope["input_digest"]),
            signature=str(prior_envelope["signature"]),
            key_id=str(prior_envelope["key_id"]),
            alg=str(prior_envelope.get("alg", "Ed25519")),
        )
        public_key = bytes.fromhex(prior_public_key)
    except (KeyError, TypeError, ValueError):
        return {"error": "prior_envelope_invalid"}
    if not verify_envelope(envelope, public_key):
        return {"error": "prior_signature_invalid"}
    return None


def _publish_authority(
    authority: object,
) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    if not isinstance(authority, Mapping):
        return None, {"error": "authority_invalid"}
    profile = authority.get("profile")
    if profile != PROFILE_PUBLISH:
        return None, {
            "error": "publish_profile_required",
            "profile": profile,
            "expected": PROFILE_PUBLISH,
        }
    # Strip constellation-level profile before the protocol star (unknown field).
    cleaned = {key: value for key, value in authority.items() if key != "profile"}
    return cleaned, None


def _assess_witness(
    authority: Mapping[str, object],
    *,
    manifest_digest: str,
    require_witness: bool,
) -> dict[str, object]:
    witness = authority.get("witness")
    has_witness = witness is not None
    if not has_witness:
        if require_witness:
            return {
                "required": True,
                "present": False,
                "verified": False,
                "status": "awaiting",
                "mode": "awaiting_witness",
            }
        return {
            "required": False,
            "present": False,
            "verified": False,
            "status": "skipped",
            "optional": True,
        }

    # Re-run write-authority with witness fields so the protocol star verifies.
    result = write_authority_check(manifest_digest, dict(authority))
    if "error" in result:
        return {
            "required": require_witness,
            "present": True,
            "verified": False,
            "status": "error",
            "detail": result,
        }
    if not bool(result.get("authorized")) or not bool(result.get("witness_verified")):
        return {
            "required": require_witness,
            "present": True,
            "verified": False,
            "status": "invalid",
            "codes": result.get("codes", []),
        }
    return {
        "required": require_witness,
        "present": True,
        "verified": True,
        "status": "verified",
    }


def _seal(
    *,
    disposition: str,
    stages: Mapping[str, object],
) -> dict[str, object]:
    policy_digest, release = _composite_identity()
    return {
        "constellation": CONSTELLATION,
        "disposition": disposition,
        "chain": "signed-envelope-chain",
        "policy_digest": policy_digest,
        "release": release,
        "stages": dict(stages),
        "components": list(_COMPONENTS),
        "limitations": list(_LIMITATIONS),
        "two_phase": {
            "edit": _PRIOR_CONSTELLATION,
            "publish": CONSTELLATION,
        },
    }


def _composite_identity() -> tuple[str, dict[str, str]]:
    """Match ADR 0007 composite_receipt_fields from the frozen policy graph."""
    from catalog.constellation import policy_for

    graph = policy_for(CONSTELLATION)
    if graph is None:
        return "sha256:missing-policy", {"digest": "sha256:missing", "key_id": "missing"}
    blob = json.dumps(
        {
            "constellation": CONSTELLATION,
            "nodes": [node.id for node in graph.nodes],
            "edges": [(edge.source, edge.target, edge.kind) for edge in graph.edges],
            "release": {
                "digest": graph.release_digest,
                "key_id": graph.release_key_id,
            },
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = "sha256:" + hashlib.sha256(blob.encode()).hexdigest()
    return digest, {"digest": graph.release_digest, "key_id": graph.release_key_id}
