"""Tests for orrery/patch-capture — pure protocol star (#222)."""

from __future__ import annotations

import hashlib
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from dogfood import verify_receipt as verify_envelope_wire
from stars.builtins import builtin_registry
from stars.patch_capture.contract import tool_schemas
from stars.patch_capture.corpus import CORPUS
from stars.patch_capture.service import capture, patch_digest
from stars.patch_capture.skill import build_skill
from tests.stars.helpers import (
    assert_manifest_publish_corpus,
    assert_payload_keys,
    assert_tool_schema_keys,
    load_star_manifest,
)

BEFORE = {
    "files": [
        {
            "path": "docs/readme.md",
            "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "size": 5,
            "content": "hello",
        },
        {
            "path": "docs/gone.md",
            "sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
            "size": 4,
            "content": "bye!",
        },
    ]
}
AFTER = {
    "files": [
        {
            "path": "docs/readme.md",
            "sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "size": 11,
            "content": "hello\nworld",
        },
        {
            "path": "docs/new.md",
            "sha256": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
            "size": 3,
            "content": "new",
        },
    ]
}

GOLDEN_CHANGE_ROWS = [
    {
        "path": "docs/gone.md",
        "before_sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        "after_sha256": None,
        "before_size": 4,
        "after_size": None,
    },
    {
        "path": "docs/new.md",
        "before_sha256": None,
        "after_sha256": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
        "before_size": None,
        "after_size": 3,
    },
    {
        "path": "docs/readme.md",
        "before_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "after_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "before_size": 5,
        "after_size": 11,
    },
]
GOLDEN_PATCH_DIGEST = hashlib.sha256(
    json.dumps(
        GOLDEN_CHANGE_ROWS,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
).hexdigest()


@pytest.mark.issue(222)
def test_golden_patch_digest_stability() -> None:
    first = capture(BEFORE, AFTER)
    second = capture(BEFORE, AFTER)
    assert first["patch_digest"] == second["patch_digest"] == GOLDEN_PATCH_DIGEST
    assert patch_digest(GOLDEN_CHANGE_ROWS) == GOLDEN_PATCH_DIGEST
    assert first["changed_paths"] == ["docs/gone.md", "docs/new.md", "docs/readme.md"]
    assert first["added_paths"] == ["docs/new.md"]
    assert first["removed_paths"] == ["docs/gone.md"]
    assert first["modified_paths"] == ["docs/readme.md"]
    assert first["line_stats"] == {"added": 2, "removed": 1}
    assert "content" not in json.dumps(first)


@pytest.mark.issue(222)
def test_manifest_pair_without_content_still_digests() -> None:
    before = {
        "files": [
            {
                "path": "a.txt",
                "sha256": "a" * 64,
                "size": 1,
            }
        ]
    }
    after = {
        "files": [
            {
                "path": "a.txt",
                "sha256": "b" * 64,
                "size": 2,
            }
        ]
    }
    result = capture(before, after)
    assert_payload_keys(result, ("patch_digest", "changed_paths", "line_stats"))
    assert result["changed_paths"] == ["a.txt"]
    assert result["line_stats"] == {"added": 0, "removed": 0}


@pytest.mark.issue(222)
class TestL0PatchCapture:
    def test_contract_tools_and_empty_egress(self) -> None:
        manifest = load_star_manifest("patch_capture")
        assert manifest["policy"]["allowed_egress"] == []
        assert_tool_schema_keys(tool_schemas(), {"capture"})
        assert_manifest_publish_corpus("patch_capture")
        assert CORPUS

    def test_invalid_snapshot_fails_loud(self) -> None:
        assert capture({}, AFTER)["error"] == "snapshot_invalid"


@pytest.mark.issue(222)
def test_envelope_and_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    private = Ed25519PrivateKey.generate()
    monkeypatch.setenv("ORRERY_STAR_PRIVATE_KEY", private.private_bytes_raw().hex())
    monkeypatch.setenv("ORRERY_STAR_KEY_ID", "stars-2026-08")
    skill = build_skill()
    envelope = next(item for item in skill._pending if item.name == "capture").handler(
        before=BEFORE,
        after=AFTER,
    )
    assert verify_envelope_wire(envelope.to_wire(), skill=skill) is True
    assert envelope.payload["patch_digest"] == GOLDEN_PATCH_DIGEST
    definition = next(item for item in builtin_registry() if item.name == "orrery/patch-capture")
    assert definition.direct_mcp_path == "/stars/patch-capture/mcp"
