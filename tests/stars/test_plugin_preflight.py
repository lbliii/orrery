"""Tests for orrery/plugin-preflight — Agent Plugins 1.0.0 sensor (#535)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from dogfood import verify_receipt as verify_envelope_wire
from stars.builtins import builtin_registry
from stars.plugin_preflight.contract import (
    MCP_SCHEMA_ID,
    PLUGIN_SCHEMA_ID,
    PROFILE_V1,
    tool_schemas,
)
from stars.plugin_preflight.corpus import CORPUS
from stars.plugin_preflight.service import check
from stars.plugin_preflight.skill import build_skill
from tests.stars.helpers import (
    assert_manifest_publish_corpus,
    assert_payload_keys,
    assert_tool_schema_keys,
    load_star_manifest,
)

ROOT = Path(__file__).resolve().parents[2]


def _plugin(name: str = "minimal-plugin", **extra: object) -> str:
    payload = {"$schema": PLUGIN_SCHEMA_ID, "name": name, **extra}
    return json.dumps(payload)


def _mcp(servers: dict[str, object]) -> str:
    return json.dumps({"$schema": MCP_SCHEMA_ID, "mcpServers": servers})


def _skill_md(name: str, description: str = "A skill.") -> str:
    return f"---\nname: {name}\ndescription: {description}\n---\n\nBody.\n"


@pytest.mark.issue(535)
def test_minimal_valid_plugin_passes() -> None:
    result = check([{"path": "plugin.json", "content": _plugin()}])
    assert_payload_keys(
        result,
        ("passed", "profile", "violations", "violation_codes", "mcp_disabled"),
    )
    assert result["passed"] is True
    assert result["profile"] == PROFILE_V1
    assert result["violation_codes"] == []
    assert result["mcp_disabled"] is False


@pytest.mark.issue(535)
def test_official_orrery_package_passes() -> None:
    bundle = []
    for path in (ROOT / "plugins" / "orrery").iterdir():
        if path.is_file():
            bundle.append({"path": path.name, "content": path.read_text(encoding="utf-8")})
    result = check(bundle)
    assert result["passed"] is True
    assert result["mcp_disabled"] is False


@pytest.mark.issue(535)
def test_path_escape_rejects() -> None:
    result = check([{"path": "../plugin.json", "content": _plugin()}])
    assert result["error"] == "path_escape"


@pytest.mark.issue(535)
def test_invalid_skill_is_skipped_not_fatal() -> None:
    result = check(
        [
            {"path": "plugin.json", "content": _plugin()},
            {"path": "skills/deploy/SKILL.md", "content": "not a skill\n"},
        ]
    )
    assert result["passed"] is True
    assert result["violation_codes"] == ["skill_skipped"]


@pytest.mark.issue(535)
def test_stdio_server_is_valid() -> None:
    result = check(
        [
            {"path": "plugin.json", "content": _plugin()},
            {
                "path": "mcp.json",
                "content": _mcp(
                    {
                        "local-validator": {
                            "type": "stdio",
                            "command": "./bin/validator",
                            "cwd": "${PLUGIN_ROOT}",
                        }
                    }
                ),
            },
        ]
    )
    assert result["passed"] is True
    assert result["mcp_disabled"] is False
    assert result["violation_codes"] == []


@pytest.mark.issue(535)
def test_schema_mismatch_disables_mcp_only() -> None:
    result = check(
        [
            {"path": "plugin.json", "content": _plugin()},
            {
                "path": "mcp.json",
                "content": json.dumps(
                    {
                        "$schema": "https://agent-plugins.org/schemas/9.9.9/mcp.schema.json",
                        "mcpServers": {},
                    }
                ),
            },
        ]
    )
    assert result["passed"] is True
    assert result["mcp_disabled"] is True
    assert result["violation_codes"] == ["mcp_schema_mismatch"]


@pytest.mark.issue(535)
def test_unknown_profile_fails_loud() -> None:
    result = check(
        [{"path": "plugin.json", "content": _plugin()}],
        profile="agent-plugins/0.0.0",
    )
    assert result["error"] == "profile_unknown"


@pytest.mark.issue(535)
def test_missing_plugin_json_is_fatal() -> None:
    result = check([{"path": "README.md", "content": "hi\n"}])
    assert result["passed"] is False
    assert result["violation_codes"] == ["plugin_json_missing"]


@pytest.mark.issue(535)
def test_secret_like_header_is_advisory() -> None:
    result = check(
        [
            {"path": "plugin.json", "content": _plugin()},
            {
                "path": "mcp.json",
                "content": _mcp(
                    {
                        "remote": {
                            "type": "streamable-http",
                            "url": "https://example.com/mcp",
                            "headers": {"Authorization": "Bearer secret"},
                        }
                    }
                ),
            },
        ]
    )
    assert result["passed"] is True
    assert "secret_like_header" in result["violation_codes"]
    assert result["advisory_codes"] == ["secret_like_header"]


@pytest.mark.issue(535)
class TestL0PluginPreflight:
    def test_contract_tools_and_empty_egress(self) -> None:
        manifest = load_star_manifest("plugin_preflight")
        assert manifest["policy"]["allowed_egress"] == []
        assert_tool_schema_keys(tool_schemas(), {"check"})
        assert_manifest_publish_corpus("plugin_preflight")
        assert CORPUS


@pytest.mark.issue(535)
def test_envelope_and_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    private = Ed25519PrivateKey.generate()
    monkeypatch.setenv("ORRERY_STAR_PRIVATE_KEY", private.private_bytes_raw().hex())
    monkeypatch.setenv("ORRERY_STAR_KEY_ID", "stars-2026-08")
    skill = build_skill()
    envelope = next(item for item in skill._pending if item.name == "check").handler(
        files=[{"path": "plugin.json", "content": _plugin()}],
        profile=PROFILE_V1,
    )
    assert verify_envelope_wire(envelope.to_wire(), skill=skill) is True
    definition = next(
        item for item in builtin_registry() if item.name == "orrery/plugin-preflight"
    )
    assert definition.direct_mcp_path == "/stars/plugin-preflight/mcp"
