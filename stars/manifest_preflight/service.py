"""Pure preflight of caller-supplied manifests against named policies."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from stars.manifest_bind.service import bind as bind_manifest

from .contract import (
    KNOWN_POLICIES,
    MAX_FILES,
    POLICY_DOCS_ONLY,
    POLICY_MAX_100,
    SHA256_HEX_LEN,
)

_DOCS_PREFIXES = ("docs/",)
_DOCS_SUFFIXES = (".md", ".rst", ".txt", ".toml", ".yaml", ".yml", ".json")

# Advisory fix text for agents — does not change pass/fail or codes.
_REMEDIATION: dict[str, str] = {
    "too_many_files": (
        "Reduce the admitted file count to at most 100, or choose a policy "
        "that allows more files."
    ),
    "path_not_docs": (
        "Move the file under docs/ with a docs-like suffix (.md, .rst, .txt, "
        ".toml, .yaml, .yml, .json), or remove it from the manifest."
    ),
    "policy_unknown": (
        "Use a known versioned policy name from the tool schema enum."
    ),
}


def _violation(code: str, **extra: object) -> dict[str, object]:
    item: dict[str, object] = {"code": code, "remediation": _REMEDIATION[code]}
    item.update(extra)
    return item


def check(
    files: object,
    policy: object,
    manifest_digest: object | None = None,
) -> dict[str, object]:
    """Evaluate pass/fail + violation codes for a named policy over caller bytes."""
    if not isinstance(policy, str) or policy not in KNOWN_POLICIES:
        return {"error": "policy_unknown", "policy": policy}

    bound = bind_manifest(files)
    if "error" in bound:
        return bound

    if bound["excluded_count"]:
        return {
            "error": "manifest_incomplete",
            "excluded_count": bound["excluded_count"],
            "excluded": bound["excluded"],
        }

    admitted = bound["admitted"]
    assert isinstance(admitted, list)
    computed = str(bound["manifest_digest"])

    if manifest_digest is not None:
        if (
            not isinstance(manifest_digest, str)
            or len(manifest_digest) != SHA256_HEX_LEN
            or any(ch not in "0123456789abcdef" for ch in manifest_digest)
        ):
            return {"error": "manifest_digest_invalid"}
        if manifest_digest != computed:
            return {
                "error": "manifest_digest_mismatch",
                "expected": computed,
                "received": manifest_digest,
            }

    violations = _violations(policy, admitted)
    return {
        "passed": not violations,
        "policy": policy,
        "manifest_digest": computed,
        "file_count": len(admitted),
        "violations": violations,
        "violation_codes": sorted({str(item["code"]) for item in violations}),
    }


def _violations(policy: str, admitted: list[Any]) -> list[dict[str, object]]:
    if policy == POLICY_MAX_100:
        if len(admitted) > 100:
            return [
                _violation(
                    "too_many_files",
                    file_count=len(admitted),
                    max_files=100,
                )
            ]
        return []

    if policy == POLICY_DOCS_ONLY:
        violations: list[dict[str, object]] = []
        for entry in admitted:
            assert isinstance(entry, Mapping)
            path = str(entry["path"])
            if not _is_docs_path(path):
                violations.append(_violation("path_not_docs", path=path))
        return violations

    return [_violation("policy_unknown", policy=policy)]


def _is_docs_path(path: str) -> bool:
    if not any(path.startswith(prefix) for prefix in _DOCS_PREFIXES):
        return False
    lowered = path.lower()
    return any(lowered.endswith(suffix) for suffix in _DOCS_SUFFIXES)


# Re-export bound for tests that want the max-files constant alignment.
assert MAX_FILES >= 100
