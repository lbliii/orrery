"""Official Agent Plugins pointer package (#533)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = ROOT / "plugins" / "orrery"
SCHEMA_DIR = ROOT / "plugins" / "schemas" / "1.0.0"
PLUGIN_SCHEMA_ID = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
MCP_SCHEMA_ID = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"
NAME_RE = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
PLUGIN_FIELDS = {
    "$schema",
    "name",
    "version",
    "description",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
    "extensions",
}


def _load(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


@pytest.mark.issue(533)
def test_vendored_schemas_are_pinned_locally() -> None:
    plugin_schema = _load(SCHEMA_DIR / "plugin.schema.json")
    mcp_schema = _load(SCHEMA_DIR / "mcp.schema.json")
    assert plugin_schema["$id"] == PLUGIN_SCHEMA_ID
    assert mcp_schema["$id"] == MCP_SCHEMA_ID
    assert plugin_schema["required"] == ["$schema", "name"]
    assert mcp_schema["required"] == ["$schema", "mcpServers"]


@pytest.mark.issue(533)
def test_plugin_json_matches_vendored_closed_schema() -> None:
    manifest = _load(PLUGIN_ROOT / "plugin.json")
    assert set(manifest) <= PLUGIN_FIELDS
    assert manifest["$schema"] == PLUGIN_SCHEMA_ID
    name = manifest["name"]
    assert isinstance(name, str)
    assert 1 <= len(name) <= 64
    assert NAME_RE.fullmatch(name)
    assert name == "orrery"
    assert "skills" not in manifest
    assert "mcpServers" not in manifest


@pytest.mark.issue(533)
def test_mcp_json_is_single_streamable_http_pointer() -> None:
    config = _load(PLUGIN_ROOT / "mcp.json")
    assert set(config) == {"$schema", "mcpServers"}
    assert config["$schema"] == MCP_SCHEMA_ID
    servers = config["mcpServers"]
    assert isinstance(servers, dict)
    assert list(servers) == ["orrery"]
    server = servers["orrery"]
    assert isinstance(server, dict)
    assert set(server) == {"type", "url"}
    assert server["type"] == "streamable-http"
    assert server["url"] == "https://orrery.lol/mcp"


@pytest.mark.issue(533)
def test_package_has_no_skills_or_stdio() -> None:
    assert not (PLUGIN_ROOT / "skills").exists()
    text = (PLUGIN_ROOT / "mcp.json").read_text(encoding="utf-8")
    assert "stdio" not in text
    assert "PLUGIN_DATA" not in text
