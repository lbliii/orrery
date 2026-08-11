"""Tests for orrery/link-check-bounded — hybrid protocol star (#223)."""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from dogfood import verify_receipt as verify_envelope_wire
from stars.builtins import builtin_registry
from stars.link_check_bounded.contract import ALLOWED_ORIGINS, tool_schemas
from stars.link_check_bounded.corpus import CORPUS
from stars.link_check_bounded.service import check
from stars.link_check_bounded.skill import build_skill
from tests.stars.helpers import (
    assert_egress_covers_url,
    assert_manifest_publish_corpus,
    assert_payload_keys,
    assert_tool_schema_keys,
    load_star_manifest,
)


def _transport_ok(url: str, *, timeout: float) -> tuple[str, int]:
    del timeout
    return url, 200


@pytest.mark.issue(223)
def test_allowlisted_link_ok() -> None:
    result = check(
        [
            {
                "path": "docs/readme.md",
                "content": "See [docs](https://example.com/docs).",
                "format": "markdown",
            }
        ],
        max_link_count=5,
        transport=_transport_ok,
    )
    assert_payload_keys(result, ("links", "link_count", "max_link_count", "passed"))
    assert result["link_count"] == 1
    assert result["passed"] is True
    assert result["links"][0]["status"] == "ok"


@pytest.mark.issue(223)
def test_over_cap_fails_loud_without_egress() -> None:
    calls: list[str] = []

    def tracking(url: str, *, timeout: float) -> tuple[str, int]:
        del timeout
        calls.append(url)
        return url, 200

    result = check(
        [
            {
                "path": "docs/a.md",
                "content": (
                    "[a](https://example.com/a) [b](https://example.com/b) "
                    "[c](https://example.com/c)"
                ),
            }
        ],
        max_link_count=2,
        transport=tracking,
    )
    assert result["error"] == "link_count_exceeded"
    assert result["link_count"] == 3
    assert calls == []


@pytest.mark.issue(223)
def test_out_of_allowlist_status() -> None:
    result = check(
        [
            {
                "path": "docs/readme.md",
                "content": "See [evil](https://evil.example/x).",
            }
        ],
        max_link_count=5,
        transport=_transport_ok,
    )
    assert result["passed"] is False
    assert result["links"][0]["status"] == "not_allowed"
    assert result["egress_count"] == 0
    remediation = result["links"][0].get("remediation")
    assert isinstance(remediation, str) and remediation.strip()


@pytest.mark.issue(314)
def test_failing_link_includes_remediation() -> None:
    result = check(
        [
            {
                "path": "docs/readme.md",
                "content": "See [evil](https://evil.example/x).",
            }
        ],
        max_link_count=5,
        transport=_transport_ok,
    )
    assert result["passed"] is False
    link = result["links"][0]
    assert link["status"] == "not_allowed"
    remediation = link.get("remediation")
    assert isinstance(remediation, str) and remediation.strip()
    assert "allowlisted" in remediation.lower()


@pytest.mark.issue(223)
class TestL0LinkCheckBounded:
    def test_contract_tools_and_egress(self) -> None:
        manifest = load_star_manifest("link_check_bounded")
        assert manifest["policy"]["allowed_egress"] == list(ALLOWED_ORIGINS)
        for origin in ALLOWED_ORIGINS:
            assert_egress_covers_url(manifest["policy"]["allowed_egress"], origin + "/")
        assert_tool_schema_keys(tool_schemas(), {"check"})
        assert_manifest_publish_corpus("link_check_bounded")
        assert CORPUS
        assert len(CORPUS) >= 1

    def test_invalid_max_fails_loud(self) -> None:
        assert check([], max_link_count=0)["error"] == "max_link_count_invalid"  # type: ignore[arg-type]


@pytest.mark.issue(223)
def test_envelope_signs_and_verifies(monkeypatch: pytest.MonkeyPatch) -> None:
    private = Ed25519PrivateKey.generate()
    monkeypatch.setenv("ORRERY_STAR_PRIVATE_KEY", private.private_bytes_raw().hex())
    monkeypatch.setenv("ORRERY_STAR_KEY_ID", "stars-2026-08")
    skill = build_skill()
    # Skill path uses live transport; feed a not_allowed URL to stay offline.
    envelope = next(item for item in skill._pending if item.name == "check").handler(
        files=[
            {
                "path": "docs/readme.md",
                "content": "See [x](https://evil.example/x).",
            }
        ],
        max_link_count=5,
    )
    assert verify_envelope_wire(envelope.to_wire(), skill=skill) is True
    assert envelope.payload["link_count"] == 1


@pytest.mark.issue(223)
def test_package_contract_and_registry() -> None:
    assert {item.name for item in build_skill()._pending} == {"check"}
    definition = next(
        item for item in builtin_registry() if item.name == "orrery/link-check-bounded"
    )
    assert definition.direct_mcp_path == "/stars/link-check-bounded/mcp"
    assert definition.publish_corpus.endswith(".corpus:CORPUS")
