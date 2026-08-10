"""Tests for MigrationProfile v1 (ADR 0008) — issue #166."""

from __future__ import annotations

import hashlib
import unicodedata

import pytest

from stars._core.migration_profile import (
    PROFILE_SCHEMA_VERSION,
    compute_profile_digest,
    require_profile,
    resolve_floating_request,
    validate_profile,
    validate_version_pin,
)

MYST_PROFILE_BASE = {
    "schema_version": PROFILE_SCHEMA_VERSION,
    "profile_id": "docs/myst-to-mdx-baseline",
    "version": "1.0.0",
    "source": {"kind": "myst-markdown", "version": "1.3.0"},
    "target": {"kind": "mdx", "version": "3.0.0"},
    "feature_vocabulary": {
        "supported": [
            {"id": "md.heading", "class": "safe"},
            {"id": "myst.directive.admonition", "class": "transformable"},
        ],
        "unsupported": [{"id": "myst.directive.include", "class": "decision_required"}],
    },
    "compatibility_policy": {
        "policy_id": "docs-mdx-baseline-v1",
        "default_action": "report",
        "rules": [
            {"id": "nav.link.break", "severity": "breaking", "action": "decision_required"},
        ],
    },
    "execution_locality": "agent_local",
    "transformer": {
        "name": "orrery/docs-myst-to-mdx",
        "version": "1.0.0",
        "digest": "a" * 64,
    },
    "validator": {
        "name": "orrery/docs-mdx-validate",
        "version": "1.0.0",
        "digest": "b" * 64,
    },
    "retention_redaction": {
        "receipt_includes": ["digests", "safe_metadata", "tool_versions", "findings_summary"],
        "receipt_excludes_by_default": [
            "source_bytes",
            "target_bytes",
            "full_patch_text",
            "private_paths",
        ],
        "max_finding_message_bytes": 512,
        "max_diagnostics_bytes": 65536,
    },
}

OPENAPI_PROFILE_BASE = {
    **MYST_PROFILE_BASE,
    "profile_id": "api-spec/openapi-3-0-to-3-1-safe",
    "source": {"kind": "openapi", "version": "3.0.3"},
    "target": {"kind": "openapi", "version": "3.1.0"},
    "feature_vocabulary": {
        "supported": [{"id": "openapi.json_schema.draft2020", "class": "transformable"}],
        "unsupported": [{"id": "openapi.discriminator.mapping", "class": "unsupported"}],
    },
    "compatibility_policy": {
        "policy_id": "openapi-client-server-v1",
        "default_action": "report",
        "rules": [
            {"id": "breaking.path.remove", "severity": "breaking", "action": "block"},
            {"id": "info.description.change", "severity": "informational", "action": "allow"},
        ],
    },
    "transformer": {
        "name": "orrery/openapi-upgrade-safe",
        "version": "1.0.0",
        "digest": "c" * 64,
    },
    "validator": {
        "name": "orrery/openapi-validate",
        "version": "1.0.0",
        "digest": "d" * 64,
    },
}


def _with_digest(profile: dict[str, object]) -> dict[str, object]:
    body = dict(profile)
    body["profile_digest"] = compute_profile_digest(body)
    return body


@pytest.fixture
def myst_profile() -> dict[str, object]:
    return _with_digest(MYST_PROFILE_BASE)


@pytest.fixture
def openapi_profile() -> dict[str, object]:
    return _with_digest(OPENAPI_PROFILE_BASE)


@pytest.mark.issue(166)
def test_profile_digest_is_deterministic_and_nfc_stable(myst_profile: dict[str, object]) -> None:
    nfd_title = {"title": "cafe\u0301 baseline"}
    with_nfd = _with_digest({**MYST_PROFILE_BASE, **nfd_title})
    with_nfc = _with_digest({**MYST_PROFILE_BASE, "title": "caf\u00e9 baseline"})
    assert with_nfd["profile_digest"] == with_nfc["profile_digest"]
    assert require_profile(myst_profile)["profile_digest"] == myst_profile["profile_digest"]


@pytest.mark.issue(166)
def test_validate_profile_accepts_adr_examples(
    myst_profile: dict[str, object], openapi_profile: dict[str, object]
) -> None:
    for profile in (myst_profile, openapi_profile):
        result = validate_profile(profile)
        assert result["valid"] is True
        assert result["profile_digest"] == profile["profile_digest"]


@pytest.mark.issue(166)
def test_validate_profile_rejects_floating_pins_and_forbidden_root_keys(
    myst_profile: dict[str, object],
) -> None:
    assert validate_version_pin("latest") == "version_pin_floating"
    assert validate_version_pin("^1.0.0") == "version_pin_floating"

    bad_pin = _with_digest({**MYST_PROFILE_BASE, "target": {"kind": "mdx", "version": "latest"}})
    assert validate_profile(bad_pin)["error"] == "version_pin_floating"

    side_channel = _with_digest({**MYST_PROFILE_BASE, "custom_field": "nope"})
    assert validate_profile(side_channel)["error"] == "profile_forbidden_root_keys"

    tampered = dict(myst_profile)
    tampered["profile_digest"] = "0" * 64
    assert validate_profile(tampered)["error"] == "profile_digest_mismatch"


@pytest.mark.issue(166)
def test_resolve_floating_request_is_fail_closed(
    myst_profile: dict[str, object], openapi_profile: dict[str, object]
) -> None:
    catalog = [myst_profile, openapi_profile]
    resolved = resolve_floating_request({"family": "docs/myst-to-mdx"}, catalog)
    assert resolved["profile_id"] == "docs/myst-to-mdx-baseline"
    assert resolved["profile_digest"] == myst_profile["profile_digest"]

    no_match = resolve_floating_request({"family": "docs/unknown"}, catalog)
    assert no_match["error"] == "no_unique_profile"

    rejected = resolve_floating_request({"family": "docs/myst-to-mdx", "target": "latest"}, catalog)
    assert rejected["error"] == "floating_target_rejected"


@pytest.mark.issue(166)
def test_finding_digest_matches_sha256_of_canonical_body() -> None:
    from stars._core.migration_run import finding_digest

    digest = finding_digest("md.heading", "safe", "docs/page.md")
    expected = hashlib.sha256(
        b'{"class":"safe","feature_id":"md.heading","path":"docs/page.md"}'
    ).hexdigest()
    assert digest == expected
    assert unicodedata.normalize("NFC", "test") == "test"
