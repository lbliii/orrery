"""Pinned OpenAPI 3.0→3.1 safe transforms for the corpus-backed subset."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping, MutableMapping, Sequence
from typing import Any


def transform_document(
    content: str,
    *,
    target_version: str,
    allow_draft_bump: bool,
) -> str:
    """Upgrade one OpenAPI JSON document; preserve unsupported constructs."""
    if not allow_draft_bump:
        return content.replace("\r\n", "\n")

    try:
        document = json.loads(content)
    except json.JSONDecodeError:
        return content.replace("\r\n", "\n")

    if not isinstance(document, dict):
        return content.replace("\r\n", "\n")

    upgraded = copy.deepcopy(document)
    upgraded["openapi"] = target_version
    _convert_nullable(upgraded)
    # Preserve caller formatting style when possible: indent=2 + trailing newline.
    return json.dumps(upgraded, indent=2, ensure_ascii=False) + "\n"


def target_openapi_parseable(targets: Sequence[Mapping[str, str]]) -> dict[str, object]:
    """Lightweight OpenAPI 3.1 parse check until api-spec/openapi-validate (#177).

    Safe corpus outputs must declare openapi 3.1.x, parse as JSON objects, and
    not leave ``nullable: true`` (converted as part of the draft bump).
    """
    findings: list[dict[str, object]] = []
    for entry in targets:
        path = entry["path"]
        content = entry["content"]
        try:
            document = json.loads(content)
        except json.JSONDecodeError as exc:
            findings.append(
                {
                    "feature_id": "openapi.document.malformed",
                    "class": "malformed",
                    "path": path,
                    "message": f"invalid JSON: {exc.msg}",
                }
            )
            continue

        if not isinstance(document, dict):
            findings.append(
                {
                    "feature_id": "openapi.document.malformed",
                    "class": "malformed",
                    "path": path,
                    "message": "OpenAPI root must be an object",
                }
            )
            continue

        version = document.get("openapi")
        if not isinstance(version, str) or not version.startswith("3.1"):
            findings.append(
                {
                    "feature_id": "openapi.version",
                    "class": "malformed",
                    "path": path,
                    "message": f"expected openapi 3.1.x, got {version!r}",
                }
            )

        residual = _find_nullable_true(document)
        for pointer in residual:
            findings.append(
                {
                    "feature_id": "openapi.nullable",
                    "class": "malformed",
                    "path": path,
                    "message": f"unconverted nullable at {pointer}",
                }
            )

    return {
        "passed": not findings,
        "findings": findings,
        "validator": {
            "name": "orrery/openapi-validate-baseline-stub",
            "version": "0.1.0",
        },
    }


def _convert_nullable(node: Any) -> None:
    if isinstance(node, dict):
        if node.get("nullable") is True:
            _apply_nullable_true(node)
        for value in list(node.values()):
            _convert_nullable(value)
    elif isinstance(node, list):
        for item in node:
            _convert_nullable(item)


def _apply_nullable_true(node: MutableMapping[str, Any]) -> None:
    del node["nullable"]
    existing = node.get("type")
    if isinstance(existing, str):
        if existing == "null":
            return
        node["type"] = [existing, "null"]
        return
    if isinstance(existing, list):
        types = [item for item in existing if isinstance(item, str)]
        if "null" not in types:
            types.append("null")
        node["type"] = types
        return
    node["type"] = "null"


def _find_nullable_true(node: Any, pointer: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(node, dict):
        if node.get("nullable") is True:
            found.append(pointer or "/")
        for key, value in node.items():
            child = f"{pointer}/{_escape(key)}" if pointer else f"/{_escape(key)}"
            found.extend(_find_nullable_true(value, child))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            child = f"{pointer}/{index}"
            found.extend(_find_nullable_true(value, child))
    return found


def _escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")
