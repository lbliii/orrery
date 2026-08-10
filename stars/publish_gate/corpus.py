from chirp.skill.smoke import CorpusPrompt

from stars.write_authority_check.contract import POLICY_EXPLICIT_PATHS
from stars.write_authority_check.service import grant_digest

_PATHS = ["docs/readme.md"]
_DIGEST = grant_digest(POLICY_EXPLICIT_PATHS, _PATHS)

#: Structural prior seal from the edit phase (#215). Signature verify is optional
#: when ``prior_public_key`` is omitted (corpus / local smoke).
_PRIOR_ENVELOPE = {
    "payload": {
        "constellation": "orrery/authorized-content-patch",
        "disposition": "authorized",
        "chain": "signed-envelope-chain",
        "policy_digest": "sha256:corpus-prior",
        "release": {
            "digest": "sha256:authorized-content-patch…",
            "key_id": "orrery-authorized-content-patch-1",
        },
        "stages": {
            "manifest-bind": {
                "manifest_digest": "a" * 64,
            },
            "write-authority-check": {"authorized": True},
            "patch-capture": {
                "patch_digest": "b" * 64,
                "changed_paths": list(_PATHS),
            },
        },
        "components": [],
        "limitations": [],
        "live_at_call": False,
    },
    "skill": "authorized-content-patch",
    "version": "0.1.0",
    "tool": "run",
    "nonce": "corpus-publish-gate-1",
    "input_digest": "c" * 64,
    "signature": "d" * 128,
    "key_id": "orrery-authorized-content-patch-1",
    "alg": "Ed25519",
}

CORPUS = (
    CorpusPrompt(
        id="publish-gate-release-seal",
        prompt="Seal a publish-authority release over a prior authorized edit envelope.",
        tool="run",
        arguments={
            "prior_envelope": dict(_PRIOR_ENVELOPE),
            "authority": {
                "profile": "publish",
                "policy": POLICY_EXPLICIT_PATHS,
                "allowed_paths": list(_PATHS),
                "grant_digest": _DIGEST,
            },
            "require_witness": False,
        },
        required_facts=(
            "orrery/publish-gate",
            "disposition",
            "stages",
        ),
    ),
)
