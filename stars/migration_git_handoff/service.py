"""Authorized local Git/PR handoff for sealed migration bundles (#180).

Orrery verifies digests and authority, then emits a digest-only handoff receipt.
It never holds repository credentials, applies patches, or performs merges.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from stars._core.migration_profile import canonical_json, require_profile, sha256_hex
from stars._core.migration_run import PRIVATE_STATUS_KEYS, MigrationRunStore, build_change_bundle
from stars.write_authority_check.service import check as write_authority_check

from .contract import (
    HANDOFF_RECEIPT_SCHEMA_VERSION,
    KNOWN_AUTHORITY_POLICIES,
    KNOWN_REPO_POLICIES,
    MAX_BRANCH_LEN,
    MAX_PATH_LEN,
    MAX_POLICY_LEN,
    MAX_PR_REF_LEN,
    MAX_ROOTS,
    POLICY_MIGRATION_HANDOFF,
    PRIVATE_RECEIPT_KEYS,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_PATH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")


class MigrationGitHandoffError(ValueError):
    """Handoff verification failed closed."""


def handoff(
    profile: object,
    change_bundle: object,
    repo_identity_policy: object,
    checkout_root: object,
    authority: object,
    local_validation: object,
    branch_or_pr_ref: object,
    *,
    sealed_validation_digest: object = None,
    composite_receipt_digest: object = None,
    store: MigrationRunStore | None = None,
    replay_key: str | None = None,
    clock: Any | None = None,
) -> dict[str, object]:
    """Verify a sealed bundle and emit a digest-only Git/PR handoff receipt."""
    if not isinstance(profile, Mapping):
        return {"error": "profile_invalid"}
    pinned = require_profile(profile)
    if "error" in pinned:
        return dict(pinned)

    bundle, bundle_error = _verify_sealed_bundle(change_bundle, store=store, replay_key=replay_key)
    if bundle_error is not None:
        return bundle_error
    assert bundle is not None

    repo_policy, repo_error = _verify_repo_identity_policy(repo_identity_policy)
    if repo_error is not None:
        return repo_error
    assert repo_policy is not None

    root_error = _authorize_checkout(checkout_root, repo_policy)
    if root_error is not None:
        return root_error
    assert isinstance(checkout_root, str)

    authority_result, authority_error = _verify_authority(
        authority,
        bundle=bundle,
        profile_digest=str(pinned["profile_digest"]),
        checkout_root=checkout_root,
        composite_receipt_digest=composite_receipt_digest,
        clock=clock,
    )
    if authority_error is not None:
        return authority_error
    assert authority_result is not None

    validation, validation_error = _verify_local_validation(
        local_validation,
        profile=pinned,
        bundle_digest=str(bundle["bundle_digest"]),
        sealed_validation_digest=sealed_validation_digest,
    )
    if validation_error is not None:
        return validation_error
    assert validation is not None

    branch_ref, branch_error = _normalize_branch_or_pr_ref(branch_or_pr_ref)
    if branch_error is not None:
        return branch_error
    assert branch_ref is not None

    receipt_body: dict[str, object] = {
        "schema_version": HANDOFF_RECEIPT_SCHEMA_VERSION,
        "profile_id": pinned["profile_id"],
        "profile_digest": pinned["profile_digest"],
        "repo_identity_policy": repo_policy,
        "checkout_root_digest": sha256_hex(checkout_root.encode("utf-8")),
        "bundle_digest": bundle["bundle_digest"],
        "local_validation_digest": validation["validation_digest"],
        "branch_or_pr_ref": branch_ref,
        "authority_result": authority_result,
    }
    if isinstance(composite_receipt_digest, str) and _SHA256_RE.fullmatch(composite_receipt_digest):
        receipt_body["composite_receipt_digest"] = composite_receipt_digest

    leak = _find_private_keys(receipt_body)
    if leak:
        return {"error": "receipt_private_field", "field": leak[0]}

    receipt_body["handoff_receipt_digest"] = compute_handoff_receipt_digest(receipt_body)
    return {"handoff_receipt": receipt_body, "authorized": True}


def compute_handoff_receipt_digest(receipt: Mapping[str, Any]) -> str:
    """Content-address the handoff receipt excluding the digest field itself."""
    without = {
        key: value for key, value in receipt.items() if key != "handoff_receipt_digest"
    }
    return sha256_hex(canonical_json(without))


def verify_handoff_receipt(receipt: Mapping[str, Any]) -> dict[str, object]:
    """Offline verify a handoff receipt digest and required field shape."""
    if not isinstance(receipt, Mapping):
        return {"verified": False, "error": "receipt_not_object"}

    required = (
        "schema_version",
        "profile_id",
        "profile_digest",
        "repo_identity_policy",
        "checkout_root_digest",
        "bundle_digest",
        "local_validation_digest",
        "branch_or_pr_ref",
        "authority_result",
        "handoff_receipt_digest",
    )
    missing = [key for key in required if key not in receipt]
    if missing:
        return {"verified": False, "error": "missing_fields", "missing": missing}

    if receipt.get("schema_version") != HANDOFF_RECEIPT_SCHEMA_VERSION:
        return {"verified": False, "error": "schema_version"}

    expected = compute_handoff_receipt_digest(receipt)
    if receipt.get("handoff_receipt_digest") != expected:
        return {
            "verified": False,
            "error": "handoff_receipt_digest_mismatch",
            "expected": expected,
            "actual": receipt.get("handoff_receipt_digest"),
        }

    leak = _find_private_keys(receipt)
    if leak:
        return {"verified": False, "error": "private_field_present", "field": leak[0]}

    return {"verified": True}


def _verify_sealed_bundle(
    change_bundle: object,
    *,
    store: MigrationRunStore | None,
    replay_key: str | None,
) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    if not isinstance(change_bundle, Mapping):
        return None, {"error": "change_bundle_invalid"}

    for key in PRIVATE_STATUS_KEYS | PRIVATE_RECEIPT_KEYS:
        if key in change_bundle:
            return None, {"error": "bundle_unsealed", "field": key}

    required = ("plan_digest", "patch_digest", "file_entries", "mapping_digest", "bundle_digest")
    missing = [key for key in required if key not in change_bundle]
    if missing:
        return None, {"error": "bundle_unsealed", "missing": missing}

    claimed = change_bundle.get("bundle_digest")
    if not isinstance(claimed, str) or not _SHA256_RE.fullmatch(claimed):
        return None, {"error": "bundle_digest_invalid"}

    recomputed = build_change_bundle(
        plan_digest=str(change_bundle["plan_digest"]),
        patch_digest=str(change_bundle["patch_digest"]),
        file_entries=list(change_bundle["file_entries"]),
        mapping_digest=str(change_bundle["mapping_digest"]),
        warnings=list(change_bundle.get("warnings") or []),
    )
    if recomputed["bundle_digest"] != claimed:
        return None, {"error": "bundle_digest_mismatch", "reason": "replay_incompatible"}

    if store is not None:
        if not replay_key:
            return None, {"error": "replay_key_required"}
        sealed = store.get(replay_key, "apply")
        if sealed is None:
            return None, {"error": "bundle_unsealed", "reason": "not_in_store"}
        if sealed.get("bundle_digest") != claimed:
            return None, {"error": "bundle_digest_mismatch", "reason": "store_drift"}

    return dict(recomputed), None


def _verify_repo_identity_policy(
    repo_identity_policy: object,
) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    if not isinstance(repo_identity_policy, Mapping):
        return None, {"error": "repo_identity_policy_invalid"}

    unknown = set(repo_identity_policy) - {"policy", "allowed_roots", "policy_digest"}
    if unknown:
        return None, {"error": "repo_identity_policy_unknown_fields"}

    policy = repo_identity_policy.get("policy")
    if not isinstance(policy, str) or not policy or len(policy) > MAX_POLICY_LEN:
        return None, {"error": "repo_policy_invalid"}
    if policy not in KNOWN_REPO_POLICIES:
        return None, {"error": "repo_policy_unknown", "policy": policy}

    roots_raw = repo_identity_policy.get("allowed_roots")
    if not isinstance(roots_raw, list) or not roots_raw or len(roots_raw) > MAX_ROOTS:
        return None, {"error": "allowed_roots_invalid"}

    allowed_roots: list[str] = []
    seen: set[str] = set()
    for index, root in enumerate(roots_raw):
        if not isinstance(root, str) or not root or len(root) > MAX_PATH_LEN:
            return None, {"error": "root_invalid", "index": index}
        if root.startswith("/") or root.startswith("../") or "/../" in f"/{root}/":
            return None, {"error": "root_traversal", "root": root, "index": index}
        if not _PATH_RE.fullmatch(root):
            return None, {"error": "root_invalid", "root": root, "index": index}
        if root in seen:
            return None, {"error": "duplicate_root", "root": root, "index": index}
        seen.add(root)
        allowed_roots.append(root)

    claimed = repo_identity_policy.get("policy_digest")
    if not isinstance(claimed, str) or not _SHA256_RE.fullmatch(claimed):
        return None, {"error": "policy_digest_invalid"}

    expected = repo_policy_digest(policy, allowed_roots)
    if claimed != expected:
        return None, {"error": "policy_digest_mismatch"}

    return {
        "policy": policy,
        "allowed_roots": sorted(allowed_roots),
        "policy_digest": expected,
    }, None


def repo_policy_digest(policy: str, allowed_roots: Sequence[str]) -> str:
    """Lowercase hex sha256 over canonical ``{policy, allowed_roots}``."""
    payload = {
        "allowed_roots": sorted(str(root) for root in allowed_roots),
        "policy": policy,
    }
    return sha256_hex(canonical_json(payload))


def _authorize_checkout(
    checkout_root: object,
    repo_policy: Mapping[str, object],
) -> dict[str, object] | None:
    if not isinstance(checkout_root, str) or not checkout_root or len(checkout_root) > MAX_PATH_LEN:
        return {"error": "checkout_root_invalid"}
    if checkout_root.startswith("/") or checkout_root.startswith("../"):
        return {"error": "checkout_unauthorized", "reason": "path_traversal"}
    if "/../" in f"/{checkout_root}/":
        return {"error": "checkout_unauthorized", "reason": "path_traversal"}
    if not _PATH_RE.fullmatch(checkout_root):
        return {"error": "checkout_unauthorized", "reason": "path_invalid"}
    if "://" in checkout_root or "@" in checkout_root:
        return {"error": "checkout_unauthorized", "reason": "embedded_secret_or_url"}

    allowed = repo_policy.get("allowed_roots")
    if not isinstance(allowed, list):
        return {"error": "checkout_unauthorized", "reason": "policy_invalid"}

    allowed_set = {str(root) for root in allowed}
    if checkout_root not in allowed_set:
        return {"error": "checkout_unauthorized", "reason": "root_not_allowed"}

    return None


def _verify_authority(
    authority: object,
    *,
    bundle: Mapping[str, object],
    profile_digest: str,
    checkout_root: str,
    composite_receipt_digest: object,
    clock: Any | None,
) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    if not isinstance(authority, Mapping):
        return None, {"error": "authority_invalid"}

    unknown = set(authority) - {
        "policy",
        "allowed_paths",
        "grant_digest",
        "witness",
        "witness_public_key",
        "expires_at",
    }
    if unknown:
        return None, {"error": "authority_unknown_fields"}

    policy = authority.get("policy")
    if policy == POLICY_MIGRATION_HANDOFF:
        return _verify_migration_handoff_authority(
            authority,
            bundle=bundle,
            profile_digest=profile_digest,
            checkout_root=checkout_root,
            composite_receipt_digest=composite_receipt_digest,
            clock=clock,
        )

    # Fallback: explicit path grant checked against bundle file paths.
    manifest_digest = str(bundle["bundle_digest"])
    if isinstance(composite_receipt_digest, str) and _SHA256_RE.fullmatch(composite_receipt_digest):
        manifest_digest = composite_receipt_digest

    result = write_authority_check(manifest_digest, authority)
    if "error" in result:
        return None, dict(result)
    if not bool(result.get("authorized")):
        return None, {
            "error": "authority_denied",
            "codes": list(result.get("codes") or []),
        }

    paths = _bundle_paths(bundle)
    allowed = result.get("allowed_paths")
    if isinstance(allowed, list):
        allowed_set = {str(path) for path in allowed}
        uncovered = sorted(path for path in paths if path not in allowed_set)
        if uncovered:
            return None, {
                "error": "authority_denied",
                "codes": ["path_not_granted"],
                "uncovered_paths": uncovered,
            }

    safe_result = {
        "authorized": True,
        "policy": result.get("policy"),
        "grant_digest": result.get("grant_digest"),
        "manifest_digest": manifest_digest,
        "witness_verified": bool(result.get("witness_verified")),
    }
    return safe_result, None


def _verify_migration_handoff_authority(
    authority: Mapping[str, object],
    *,
    bundle: Mapping[str, object],
    profile_digest: str,
    checkout_root: str,
    composite_receipt_digest: object,
    clock: Any | None,
) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    policy = authority.get("policy")
    if policy not in KNOWN_AUTHORITY_POLICIES:
        return None, {"error": "authority_policy_unknown", "policy": policy}

    expires_at = authority.get("expires_at")
    if expires_at is not None:
        if not isinstance(expires_at, str):
            return None, {"error": "authority_expired", "reason": "expires_at_invalid"}
        try:
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=UTC)
        except ValueError:
            return None, {"error": "authority_expired", "reason": "expires_at_invalid"}
        now = clock() if clock is not None else datetime.now(UTC)
        if now >= expiry:
            return None, {"error": "authority_expired", "reason": "past_expiry"}

    claimed = authority.get("grant_digest")
    if not isinstance(claimed, str) or not _SHA256_RE.fullmatch(claimed):
        return None, {"error": "grant_digest_invalid"}

    bundle_digest = str(bundle["bundle_digest"])
    composite = (
        str(composite_receipt_digest)
        if isinstance(composite_receipt_digest, str)
        and _SHA256_RE.fullmatch(composite_receipt_digest)
        else None
    )
    expected = migration_handoff_grant_digest(
        bundle_digest=bundle_digest,
        profile_digest=profile_digest,
        checkout_root=checkout_root,
        composite_receipt_digest=composite,
    )
    if claimed != expected:
        return None, {"error": "grant_digest_mismatch"}

    return {
        "authorized": True,
        "policy": policy,
        "grant_digest": expected,
        "bundle_digest": bundle_digest,
        "profile_digest": profile_digest,
        "checkout_root_digest": sha256_hex(checkout_root.encode("utf-8")),
        "composite_receipt_digest": composite,
    }, None


def migration_handoff_grant_digest(
    *,
    bundle_digest: str,
    profile_digest: str,
    checkout_root: str,
    composite_receipt_digest: str | None = None,
) -> str:
    """Digest binding bundle, profile, checkout root, and optional composite receipt."""
    payload: dict[str, object] = {
        "bundle_digest": bundle_digest,
        "checkout_root_digest": sha256_hex(checkout_root.encode("utf-8")),
        "policy": POLICY_MIGRATION_HANDOFF,
        "profile_digest": profile_digest,
    }
    if composite_receipt_digest is not None:
        payload["composite_receipt_digest"] = composite_receipt_digest
    return sha256_hex(canonical_json(payload))


def _verify_local_validation(
    local_validation: object,
    *,
    profile: Mapping[str, Any],
    bundle_digest: str,
    sealed_validation_digest: object,
) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    if not isinstance(local_validation, Mapping):
        return None, {"error": "local_validation_invalid"}

    for key in PRIVATE_RECEIPT_KEYS | PRIVATE_STATUS_KEYS:
        if key in local_validation:
            return None, {"error": "validation_private_field", "field": key}

    validation_digest = local_validation.get("validation_digest")
    if not isinstance(validation_digest, str) or not _SHA256_RE.fullmatch(validation_digest):
        return None, {"error": "local_validation_digest_invalid"}

    if "passed" not in local_validation:
        return None, {"error": "local_validation_passed_missing"}
    passed = bool(local_validation["passed"])
    if not passed:
        return None, {"error": "validation_mismatch", "reason": "local_validation_failed"}

    validator = profile.get("validator")
    if not isinstance(validator, Mapping):
        return None, {"error": "validator_pin_missing"}

    local_validator = local_validation.get("validator")
    if isinstance(local_validator, Mapping) and local_validator != validator:
        return None, {"error": "validation_mismatch", "reason": "validator_pin"}

    local_bundle = local_validation.get("bundle_digest")
    if isinstance(local_bundle, str) and local_bundle != bundle_digest:
        return None, {"error": "validation_mismatch", "reason": "bundle_digest"}

    if sealed_validation_digest is not None:
        if not isinstance(sealed_validation_digest, str) or not _SHA256_RE.fullmatch(
            sealed_validation_digest
        ):
            return None, {"error": "sealed_validation_digest_invalid"}
        if validation_digest != sealed_validation_digest:
            return None, {"error": "validation_mismatch", "reason": "sealed_digest_drift"}

    return {
        "validation_digest": validation_digest,
        "passed": passed,
        "validator": dict(validator),
        "bundle_digest": bundle_digest,
    }, None


def _normalize_branch_or_pr_ref(
    branch_or_pr_ref: object,
) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    if not isinstance(branch_or_pr_ref, Mapping):
        return None, {"error": "branch_or_pr_ref_invalid"}

    unknown = set(branch_or_pr_ref) - {"branch", "pr_ref", "title_digest", "body_digest"}
    if unknown:
        return None, {"error": "branch_or_pr_ref_unknown_fields"}

    branch = branch_or_pr_ref.get("branch")
    pr_ref = branch_or_pr_ref.get("pr_ref")
    if branch is None and pr_ref is None:
        return None, {"error": "branch_or_pr_ref_required"}

    normalized: dict[str, object] = {}
    if branch is not None:
        if not isinstance(branch, str) or not branch or len(branch) > MAX_BRANCH_LEN:
            return None, {"error": "branch_invalid"}
        if "://" in branch or "token" in branch.lower():
            return None, {"error": "branch_invalid", "reason": "embedded_secret"}
        normalized["branch"] = branch

    if pr_ref is not None:
        if not isinstance(pr_ref, str) or not pr_ref or len(pr_ref) > MAX_PR_REF_LEN:
            return None, {"error": "pr_ref_invalid"}
        if "://" in pr_ref or "@" in pr_ref:
            return None, {"error": "pr_ref_invalid", "reason": "embedded_url_or_secret"}
        normalized["pr_ref"] = pr_ref

    for field in ("title_digest", "body_digest"):
        digest = branch_or_pr_ref.get(field)
        if digest is None:
            continue
        if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
            return None, {"error": f"{field}_invalid"}
        normalized[field] = digest

    return normalized, None


def _bundle_paths(bundle: Mapping[str, object]) -> list[str]:
    entries = bundle.get("file_entries")
    if not isinstance(entries, list):
        return []
    paths: list[str] = []
    for item in entries:
        if isinstance(item, Mapping) and isinstance(item.get("path"), str):
            paths.append(str(item["path"]))
    return sorted(paths)


def _find_private_keys(payload: Mapping[str, Any]) -> list[str]:
    found: list[str] = []

    def walk(value: object, prefix: str = "") -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                key_str = str(key)
                full = f"{prefix}.{key_str}" if prefix else key_str
                if key_str in PRIVATE_RECEIPT_KEYS | PRIVATE_STATUS_KEYS:
                    found.append(full)
                walk(item, full)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{prefix}[{index}]")

    walk(payload)
    return found
