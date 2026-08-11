"""Pinned OpenAPI 3.1 parser/schema adapter for migration validation (#177)."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from .contract import (
    VALIDATOR_NAME,
    VALIDATOR_VERSION,
    feature_finding_digest,
)


def check_openapi_targets(
    targets: Sequence[Mapping[str, str]],
    *,
    target_version: str,
) -> dict[str, object]:
    """Parse and lint target OpenAPI JSON for profile target version conformance."""
    findings: list[dict[str, object]] = []
    for entry in targets:
        path = str(entry["path"])
        content = str(entry["content"])
        try:
            document = json.loads(content)
        except json.JSONDecodeError:
            payload = {
                "feature_id": "openapi.json_schema.draft2020",
                "class": "malformed",
                "path": path,
                "message": "json parse error",
            }
            payload["finding_digest"] = feature_finding_digest(payload)
            findings.append(payload)
            continue

        if not isinstance(document, dict):
            payload = {
                "feature_id": "openapi.document.malformed",
                "class": "malformed",
                "path": path,
                "message": "OpenAPI root must be an object",
            }
            payload["finding_digest"] = feature_finding_digest(payload)
            findings.append(payload)
            continue

        version = document.get("openapi")
        major_target = _major_version(target_version)
        if not isinstance(version, str) or _major_version(version) != major_target:
            payload = {
                "feature_id": "openapi.version",
                "class": "malformed",
                "path": path,
                "message": f"expected openapi {target_version}, got {version!r}",
            }
            payload["finding_digest"] = feature_finding_digest(payload)
            findings.append(payload)

        for pointer in _find_nullable_true(document):
            payload = {
                "feature_id": "openapi.nullable",
                "class": "malformed",
                "path": path,
                "message": f"unconverted nullable at {pointer}",
            }
            payload["finding_digest"] = feature_finding_digest(payload)
            findings.append(payload)

    return {
        "passed": not findings,
        "findings": findings,
        "validator": {
            "name": VALIDATOR_NAME,
            "version": VALIDATOR_VERSION,
        },
    }


def _major_version(version: str) -> str:
    parts = version.split(".")
    if len(parts) >= 2:
        return f"{parts[0]}.{parts[1]}"
    return version


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
