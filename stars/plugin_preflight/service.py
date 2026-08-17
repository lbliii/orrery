"""Pure Agent Plugins 1.0.0 preflight over a caller file bundle."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

from stars.manifest_bind.service import bind as bind_manifest

from .contract import (
    ADVISORY_CODES,
    AUTHOR_FIELDS,
    FATAL_CODES,
    KNOWN_PROFILES,
    MAX_CONTENT_BYTES,
    MAX_FILES,
    MAX_PATH_LEN,
    MCP_SCHEMA_ID,
    PLUGIN_SCHEMA_ID,
    PLUGIN_TOP_LEVEL,
    PROFILE_V1,
    SHA256_HEX_LEN,
)

_PATH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
_NAME_RE = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
_FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
_SECRET_RE = re.compile(
    r"(authorization|api[_-]?key|token|password|secret|bearer)",
    re.IGNORECASE,
)
_LOOPBACK = frozenset({"localhost", "127.0.0.1", "::1"})

_REMEDIATION: dict[str, str] = {
    "plugin_json_missing": "Add a root plugin.json that resolves inside the plugin bundle.",
    "plugin_json_invalid": (
        "Fix plugin.json so it is a JSON object with valid required fields."
    ),
    "name_invalid": (
        "Set name to 1-64 lowercase [a-z0-9.-] characters, starting and ending "
        "alphanumeric, with no -- or .."
    ),
    "schema_unsupported": (
        "Set $schema to https://agent-plugins.org/schemas/1.0.0/plugin.schema.json."
    ),
    "path_escape": "Keep every package path inside the plugin root (no / or ../).",
    "mcp_schema_mismatch": (
        "Set mcp.json $schema to the same Agent Plugins 1.0.0 MCP identifier, "
        "or remove mcp.json."
    ),
    "skill_skipped": "Fix or remove the invalid skills/<name>/SKILL.md entry.",
    "server_skipped": "Fix or remove the invalid mcpServers entry.",
    "secret_like_header": "Remove credential-like values from mcp.json headers.",
    "secret_like_env": "Remove credential-like values from mcp.json env.",
    "profile_unknown": "Use the known profile agent-plugins/1.0.0.",
}


def check(
    files: object,
    profile: object = PROFILE_V1,
    manifest_digest: object | None = None,
) -> dict[str, object]:
    """Evaluate Agent Plugins 1.0.0 over caller-supplied file contents."""
    if not isinstance(profile, str) or profile not in KNOWN_PROFILES:
        return {"error": "profile_unknown", "profile": profile}

    parsed, error = _parse_bundle(files)
    if error is not None:
        return error

    inventory = _inventory_rows(parsed)
    bound = bind_manifest(inventory)
    if "error" in bound:
        return bound
    if bound["excluded_count"]:
        return {
            "error": "manifest_incomplete",
            "excluded_count": bound["excluded_count"],
            "excluded": bound["excluded"],
        }

    computed = str(bound["manifest_digest"])
    digest_error = _digest_claim(manifest_digest, computed)
    if digest_error is not None:
        return digest_error

    by_path = {row["path"]: row["content"] for row in parsed}
    violations: list[dict[str, object]] = []
    mcp_disabled = False

    plugin_ok, plugin_violations = _check_plugin_json(by_path)
    violations.extend(plugin_violations)
    if plugin_ok:
        mcp_disabled, mcp_violations = _check_mcp_json(by_path)
        violations.extend(mcp_violations)
        violations.extend(_check_skills(by_path))

    fatal = [item for item in violations if item["code"] in FATAL_CODES]
    codes = sorted({str(item["code"]) for item in violations})
    return {
        "passed": not fatal,
        "profile": profile,
        "manifest_digest": computed,
        "file_count": len(parsed),
        "mcp_disabled": mcp_disabled,
        "violations": violations,
        "violation_codes": codes,
        "advisory_codes": sorted(code for code in codes if code in ADVISORY_CODES),
    }


def _parse_bundle(
    files: object,
) -> tuple[list[dict[str, str]] | None, dict[str, object] | None]:
    if not isinstance(files, list) or not files or len(files) > MAX_FILES:
        return None, {"error": "files_invalid"}

    parsed: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, raw in enumerate(files):
        if not isinstance(raw, Mapping):
            return None, {"error": "entry_not_object", "index": index}
        if set(raw) - {"path", "content"}:
            return None, {"error": "entry_unknown_fields", "index": index}
        path = raw.get("path")
        content = raw.get("content")
        if not isinstance(path, str) or not path or len(path) > MAX_PATH_LEN:
            return None, {"error": "path_invalid", "index": index}
        if path.startswith("/") or path.startswith("../") or "/../" in f"/{path}/":
            return None, {
                "error": "path_escape",
                "path": path,
                "index": index,
                "violations": [_violation("path_escape", path=path)],
            }
        if not _PATH_RE.fullmatch(path):
            return None, {"error": "path_invalid", "path": path, "index": index}
        if path in seen:
            return None, {"error": "duplicate_path", "path": path, "index": index}
        if not isinstance(content, str):
            return None, {"error": "content_invalid", "path": path, "index": index}
        if len(content.encode()) > MAX_CONTENT_BYTES:
            return None, {"error": "content_too_large", "path": path, "index": index}
        seen.add(path)
        parsed.append({"path": path, "content": content})
    parsed.sort(key=lambda item: item["path"])
    return parsed, None


def _inventory_rows(parsed: list[dict[str, str]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for entry in parsed:
        raw = entry["content"].encode()
        rows.append(
            {
                "path": entry["path"],
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size": len(raw),
            }
        )
    return rows


def _digest_claim(
    manifest_digest: object | None, computed: str
) -> dict[str, object] | None:
    if manifest_digest is None:
        return None
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
    return None


def _check_plugin_json(
    by_path: Mapping[str, str],
) -> tuple[bool, list[dict[str, object]]]:
    if "plugin.json" not in by_path:
        return False, [_violation("plugin_json_missing", path="plugin.json")]
    try:
        data = json.loads(by_path["plugin.json"])
    except json.JSONDecodeError:
        return False, [_violation("plugin_json_invalid", path="plugin.json")]
    if not isinstance(data, dict):
        return False, [_violation("plugin_json_invalid", path="plugin.json")]

    violations: list[dict[str, object]] = []
    schema = data.get("$schema")
    if schema != PLUGIN_SCHEMA_ID:
        violations.append(_violation("schema_unsupported", path="plugin.json"))
    name = data.get("name")
    if not isinstance(name, str) or not name or not _NAME_RE.fullmatch(name):
        violations.append(_violation("name_invalid", path="plugin.json"))
    extra = set(data) - PLUGIN_TOP_LEVEL
    if extra:
        # Spec §5.2: report and ignore unknown fields; not fatal.
        pass
    if "author" in data and not _author_ok(data["author"]):
        violations.append(_violation("plugin_json_invalid", path="plugin.json"))
    if "keywords" in data and not _string_list(data["keywords"]):
        violations.append(_violation("plugin_json_invalid", path="plugin.json"))
    if "extensions" in data and data["extensions"] is not None:
        if not isinstance(data["extensions"], dict):
            pass
        elif any(not isinstance(value, dict) for value in data["extensions"].values()):
            violations.append(_violation("plugin_json_invalid", path="plugin.json"))
    for field in ("version", "description", "homepage", "repository", "license"):
        if field in data and not isinstance(data[field], str):
            violations.append(_violation("plugin_json_invalid", path="plugin.json"))
            break
    fatal = any(item["code"] in FATAL_CODES for item in violations)
    return (not fatal), violations


def _author_ok(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    if set(value) - AUTHOR_FIELDS:
        return False
    return all(isinstance(item, str) for item in value.values())


def _string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _check_mcp_json(
    by_path: Mapping[str, str],
) -> tuple[bool, list[dict[str, object]]]:
    if "mcp.json" not in by_path:
        return False, []
    try:
        data = json.loads(by_path["mcp.json"])
    except json.JSONDecodeError:
        return True, [_violation("mcp_schema_mismatch", path="mcp.json")]
    if not isinstance(data, dict) or set(data) - {"$schema", "mcpServers"}:
        return True, [_violation("mcp_schema_mismatch", path="mcp.json")]
    if data.get("$schema") != MCP_SCHEMA_ID:
        return True, [_violation("mcp_schema_mismatch", path="mcp.json")]
    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        return True, [_violation("mcp_schema_mismatch", path="mcp.json")]

    violations: list[dict[str, object]] = []
    for name, entry in servers.items():
        violations.extend(_check_server(name, entry))
    return False, violations


def _check_server(name: str, entry: object) -> list[dict[str, object]]:
    if not isinstance(entry, dict) or "type" not in entry:
        return [_violation("server_skipped", path="mcp.json", server=name)]
    server_type = entry.get("type")
    if server_type == "stdio":
        return _check_stdio(name, entry)
    if server_type in {"streamable-http", "sse"}:
        return _check_http(name, entry)
    return [_violation("server_skipped", path="mcp.json", server=name)]


def _check_stdio(name: str, entry: Mapping[str, Any]) -> list[dict[str, object]]:
    allowed = {"type", "command", "args", "env", "cwd"}
    if set(entry) - allowed:
        return [_violation("server_skipped", path="mcp.json", server=name)]
    command = entry.get("command")
    if not isinstance(command, str) or not command or " " in command:
        return [_violation("server_skipped", path="mcp.json", server=name)]
    if command.startswith("./"):
        if not _contained(command[2:]):
            return [
                _violation(
                    "server_skipped",
                    path="mcp.json",
                    server=name,
                    reason="path_escape",
                )
            ]
    elif command.startswith(".") or "/" in command or "\\" in command:
        return [
            _violation(
                "server_skipped",
                path="mcp.json",
                server=name,
                reason="path_escape",
            )
        ]
    if "args" in entry and not _string_list(entry["args"]):
        return [_violation("server_skipped", path="mcp.json", server=name)]
    env = entry.get("env")
    if env is not None:
        if not isinstance(env, dict) or any(not isinstance(v, str) for v in env.values()):
            return [_violation("server_skipped", path="mcp.json", server=name)]
        if "PLUGIN_ROOT" in env or "PLUGIN_DATA" in env:
            return [_violation("server_skipped", path="mcp.json", server=name)]
    if "cwd" in entry and not _cwd_ok(str(entry["cwd"])):
        return [
            _violation(
                "server_skipped",
                path="mcp.json",
                server=name,
                reason="path_escape",
            )
        ]
    advisories: list[dict[str, object]] = []
    if isinstance(env, dict):
        for key, value in env.items():
            if _SECRET_RE.search(str(key)) or _SECRET_RE.search(str(value)):
                advisories.append(
                    _violation("secret_like_env", path="mcp.json", server=name, key=key)
                )
    return advisories


def _check_http(name: str, entry: Mapping[str, Any]) -> list[dict[str, object]]:
    if set(entry) - {"type", "url", "headers"}:
        return [_violation("server_skipped", path="mcp.json", server=name)]
    url = entry.get("url")
    if not isinstance(url, str) or not _http_url_ok(url):
        return [_violation("server_skipped", path="mcp.json", server=name)]
    headers = entry.get("headers")
    if headers is None:
        return []
    if not isinstance(headers, dict) or any(not isinstance(v, str) for v in headers.values()):
        return [_violation("server_skipped", path="mcp.json", server=name)]
    lowered = [str(key).lower() for key in headers]
    if len(lowered) != len(set(lowered)):
        return [_violation("server_skipped", path="mcp.json", server=name)]
    advisories: list[dict[str, object]] = []
    for key, value in headers.items():
        if _SECRET_RE.search(str(key)) or _SECRET_RE.search(str(value)):
            advisories.append(
                _violation("secret_like_header", path="mcp.json", server=name, key=key)
            )
    return advisories


def _check_skills(by_path: Mapping[str, str]) -> list[dict[str, object]]:
    violations: list[dict[str, object]] = []
    for path, content in by_path.items():
        parts = path.split("/")
        if len(parts) != 3 or parts[0] != "skills" or parts[2] != "SKILL.md":
            continue
        if not _skill_ok(parts[1], content):
            violations.append(_violation("skill_skipped", path=path))
    return violations


def _skill_ok(directory: str, content: str) -> bool:
    match = _FRONTMATTER_RE.match(content)
    if match is None:
        return False
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip("\"'")
    name = fields.get("name")
    description = fields.get("description")
    return bool(name and description and name == directory)


def _cwd_ok(cwd: str) -> bool:
    if cwd.startswith("./"):
        return _contained(cwd[2:])
    if cwd in {"${PLUGIN_ROOT}", "${PLUGIN_DATA}"}:
        return True
    if cwd.startswith("${PLUGIN_ROOT}/"):
        return _contained(cwd[len("${PLUGIN_ROOT}/") :])
    if cwd.startswith("${PLUGIN_DATA}/"):
        return _contained(cwd[len("${PLUGIN_DATA}/") :])
    return False


def _contained(relative: str) -> bool:
    if not relative:
        return True
    if relative.startswith("/") or relative.startswith("../"):
        return False
    return "/../" not in f"/{relative}/"


def _http_url_ok(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.fragment:
        return False
    if parsed.username or parsed.password:
        return False
    host = (parsed.hostname or "").lower()
    return parsed.scheme != "http" or host in _LOOPBACK


def _violation(code: str, **extra: object) -> dict[str, object]:
    item: dict[str, object] = {"code": code, "remediation": _REMEDIATION[code]}
    item.update(extra)
    return item
