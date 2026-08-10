"""Tests for orrery/manifest-bind — pure protocol star (#222)."""

from __future__ import annotations

import hashlib
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from dogfood import verify_receipt as verify_envelope_wire
from stars.builtins import builtin_registry
from stars.manifest_bind.contract import tool_schemas
from stars.manifest_bind.corpus import CORPUS
from stars.manifest_bind.service import bind, manifest_digest
from stars.manifest_bind.skill import build_skill
from tests.stars.helpers import (
    assert_manifest_publish_corpus,
    assert_payload_keys,
    assert_tool_schema_keys,
    load_star_manifest,
)

GOLDEN_FILES = [
    {
        "path": "docs/plan.md",
        "sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "size": 34,
    },
    {
        "path": "docs/readme.md",
        "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "size": 12,
    },
]
GOLDEN_DIGEST = hashlib.sha256(
    json.dumps(
        sorted(GOLDEN_FILES, key=lambda item: item["path"]),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
).hexdigest()


@pytest.mark.issue(222)
def test_golden_digest_stability_order_independent() -> None:
    first = bind(list(reversed(GOLDEN_FILES)))
    second = bind(GOLDEN_FILES)
    assert first["manifest_digest"] == second["manifest_digest"] == GOLDEN_DIGEST
    assert first["admitted_count"] == 2
    assert first["excluded_count"] == 0
    assert manifest_digest(GOLDEN_FILES) == GOLDEN_DIGEST


@pytest.mark.issue(222)
def test_bind_excludes_invalid_and_duplicate_entries() -> None:
    result = bind(
        [
            GOLDEN_FILES[0],
            {"path": "../escape.md", "sha256": GOLDEN_FILES[0]["sha256"], "size": 1},
            {"path": GOLDEN_FILES[0]["path"], "sha256": "c" * 64, "size": 2},
            {"path": "ok.md", "sha256": "not-hex", "size": 1},
        ]
    )
    assert_payload_keys(result, ("manifest_digest", "admitted_count", "excluded_count"))
    assert result["admitted_count"] == 1
    assert result["excluded_count"] == 3
    assert {item["error"] for item in result["excluded"]} == {
        "path_traversal",
        "duplicate_path",
        "sha256_invalid",
    }


@pytest.mark.issue(222)
class TestL0ManifestBind:
    def test_contract_tools_and_empty_egress(self) -> None:
        manifest = load_star_manifest("manifest_bind")
        assert manifest["policy"]["allowed_egress"] == []
        assert_tool_schema_keys(tool_schemas(), {"bind"})
        assert_manifest_publish_corpus("manifest_bind")
        assert CORPUS

    def test_invalid_files_type_fails_loud(self) -> None:
        assert bind(None)["error"] == "files_invalid"  # type: ignore[arg-type]


@pytest.mark.issue(222)
def test_envelope_signs_and_verifies(monkeypatch: pytest.MonkeyPatch) -> None:
    private = Ed25519PrivateKey.generate()
    monkeypatch.setenv("ORRERY_STAR_PRIVATE_KEY", private.private_bytes_raw().hex())
    monkeypatch.setenv("ORRERY_STAR_KEY_ID", "stars-2026-08")
    skill = build_skill()
    envelope = next(item for item in skill._pending if item.name == "bind").handler(
        files=GOLDEN_FILES
    )
    assert verify_envelope_wire(envelope.to_wire(), skill=skill) is True
    assert envelope.payload["manifest_digest"] == GOLDEN_DIGEST


@pytest.mark.issue(222)
def test_package_contract_and_registry() -> None:
    assert {item.name for item in build_skill()._pending} == {"bind"}
    definition = next(item for item in builtin_registry() if item.name == "orrery/manifest-bind")
    assert definition.direct_mcp_path == "/stars/manifest-bind/mcp"
    assert definition.publish_corpus.endswith(".corpus:CORPUS")
