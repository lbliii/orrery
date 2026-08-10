"""Grant digest helpers matching hosted ``orrery/write-authority-check``."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Final

POLICY_EXPLICIT_PATHS: Final = "orrery/explicit-paths@v1"


def grant_digest(policy: str, allowed_paths: Sequence[str]) -> str:
    """Lowercase hex sha256 of canonical ``{policy, allowed_paths}``.

    Must match ``stars.write_authority_check.service.grant_digest``.
    """
    payload = {
        "allowed_paths": sorted(str(path) for path in allowed_paths),
        "policy": policy,
    }
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(body.encode()).hexdigest()
