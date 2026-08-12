"""Direct MCP tools/list must prefer package tool_schemas() over Chirp inference."""

from __future__ import annotations

import importlib
import json
from typing import Any

import pytest
from chirp import App
from chirp.testing import TestClient

from stars._core.direct_mcp import direct_tool_registry
from stars.builtins import build_direct_skills, builtin_registry

_META_PROTOCOL_VERSION = "io.modelcontextprotocol/protocolVersion"


def _modern_mcp_params(**extra: Any) -> dict[str, Any]:
    params: dict[str, Any] = {
        "_meta": {
            _META_PROTOCOL_VERSION: "2026-07-28",
            "io.modelcontextprotocol/clientCapabilities": {},
        },
    }
    params.update(extra)
    return params


def _modern_mcp_headers(method: str, name: str | None = None) -> dict[str, str]:
    headers = {
        "content-type": "application/json",
        "mcp-protocol-version": "2026-07-28",
        "mcp-method": method,
    }
    if name is not None:
        headers["mcp-name"] = name
    return headers


def _load_tool_schemas(python_package: str) -> dict[str, dict[str, Any]]:
    for module_name in (python_package, f"{python_package}.contract"):
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
        raw = getattr(module, "tool_schemas", None)
        if callable(raw):
            schemas = raw()
            if isinstance(schemas, dict):
                return schemas
    return {}


def _required_names(schema: dict[str, Any]) -> list[str]:
    required = schema.get("required")
    if isinstance(required, list):
        return [item for item in required if isinstance(item, str)]
    return []


def _minimal_arguments(schema: dict[str, Any]) -> dict[str, Any]:
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return {}
    names = _required_names(schema) or list(properties)
    args: dict[str, Any] = {}
    for name in names:
        prop = properties.get(name)
        if not isinstance(prop, dict):
            continue
        if "default" in prop:
            args[name] = prop["default"]
        elif prop.get("type") == "string" and isinstance(prop.get("enum"), list) and prop["enum"]:
            args[name] = prop["enum"][0]
        elif prop.get("type") == "string" and name == "ref":
            args[name] = "0" * 40
        elif prop.get("type") == "string":
            args[name] = "test"
        elif prop.get("type") == "array" and isinstance(prop.get("items"), dict):
            item = prop["items"]
            if item.get("type") == "object" and isinstance(item.get("properties"), dict):
                row = {
                    key: "x"
                    for key in item["properties"]
                    if item["properties"][key].get("type") == "string"
                }
                args[name] = [row] if row else [{}]
            else:
                args[name] = []
        elif prop.get("type") == "object":
            args[name] = {"rows": []}
        elif prop.get("type") == "boolean":
            args[name] = False
        elif prop.get("type") == "integer":
            args[name] = 1
        elif prop.get("type") == "number":
            args[name] = 1.0
    return args


def _mcp_error_message(body: dict[str, Any]) -> str:
    error = body.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        return message if isinstance(message, str) else json.dumps(error)
    return ""


@pytest.mark.issue(339)
def test_direct_mcp_input_schema_matches_tool_schemas_when_present() -> None:
    app = App("direct-mcp-schema-test")
    skills = build_direct_skills(builtin_registry())
    checked = 0
    for definition in builtin_registry():
        contracts = _load_tool_schemas(definition.python_package)
        if not contracts:
            continue
        registry = direct_tool_registry(app, definition, skills[definition.name])
        for tool_name, contract in contracts.items():
            tool = registry._tools.get(tool_name)
            assert tool is not None, f"{definition.name} missing tool {tool_name!r}"
            expected = contract.get("inputSchema")
            assert isinstance(expected, dict), f"{definition.name}/{tool_name} contract inputSchema"
            assert tool.schema == expected, f"{definition.name}/{tool_name} schema drift"
            checked += 1
    assert checked >= 30


@pytest.mark.issue(339)
@pytest.mark.parametrize(
    ("star_name", "tool_name"),
    [
        ("orrery/http-head", "head"),
        ("orrery/structure-audit", "audit"),
        ("orrery/gh-file-at-ref", "get"),
        ("orrery/board-memo", "run"),
        ("orrery/table-fresh", "run"),
    ],
)
async def test_direct_mcp_tools_list_properties_match_contract_or_runtime(
    example_app,
    star_name: str,
    tool_name: str,
) -> None:
    definition = builtin_registry().get(star_name)
    contracts = _load_tool_schemas(definition.python_package)
    async with TestClient(example_app) as client:
        listed = await client.post(
            definition.direct_mcp_path,
            json={
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": 339,
                "params": _modern_mcp_params(),
            },
            headers=_modern_mcp_headers("tools/list"),
        )
        assert listed.status == 200
        tools = {item["name"]: item for item in json.loads(listed.text)["result"]["tools"]}
        tool = tools[tool_name]
        schema = tool["inputSchema"]
        properties = schema.get("properties")
        assert isinstance(properties, dict)
        if tool_name in contracts:
            expected = contracts[tool_name]["inputSchema"]
            assert isinstance(expected, dict)
            assert schema == expected
        else:
            assert properties, f"{star_name}/{tool_name} must expose input properties"

        called = await client.post(
            definition.direct_mcp_path,
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "id": 340,
                "params": _modern_mcp_params(
                    name=tool_name,
                    arguments=_minimal_arguments(schema),
                ),
            },
            headers=_modern_mcp_headers("tools/call", tool_name),
        )
        assert called.status == 200
        body = json.loads(called.text)
        message = _mcp_error_message(body).lower()
        assert "invalid arguments" not in message
        assert "missing required" not in message
        assert "unexpected keyword" not in message
