"""Structural OpenAPI surface comparison for compatibility-diff (#176)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .contract import (
    RULE_INFO_DESCRIPTION,
    RULE_OPERATION_CHANGE,
    RULE_PATH_ADD,
    RULE_PATH_REMOVE,
    RULE_SCHEMA_ADD,
    RULE_SCHEMA_CHANGE,
    RULE_SCHEMA_REMOVE,
)

_HTTP_METHODS = frozenset({"get", "put", "post", "delete", "options", "head", "patch", "trace"})


@dataclass(frozen=True, slots=True)
class RawChange:
    rule_id: str
    kind: str
    location: str
    location_kind: str
    evidence: dict[str, object]


def parse_document(content: str) -> dict[str, Any] | None:
    try:
        document = json.loads(content)
    except json.JSONDecodeError:
        return None
    if not isinstance(document, dict):
        return None
    return document


def extract_surface(document: Mapping[str, Any]) -> dict[str, object]:
    """Stable operation/schema paths plus bounded info fields."""
    operations: dict[str, object] = {}
    paths = document.get("paths")
    if isinstance(paths, Mapping):
        for path_key, item in paths.items():
            if not isinstance(path_key, str) or not isinstance(item, Mapping):
                continue
            for method, operation in item.items():
                if not isinstance(method, str) or method.lower() not in _HTTP_METHODS:
                    continue
                pointer = f"/paths/{_escape(path_key)}/{method.lower()}"
                operations[pointer] = _operation_fingerprint(operation)

    schemas: dict[str, object] = {}
    components = document.get("components")
    if isinstance(components, Mapping):
        schema_map = components.get("schemas")
        if isinstance(schema_map, Mapping):
            for name, schema in schema_map.items():
                if not isinstance(name, str):
                    continue
                pointer = f"/components/schemas/{_escape(name)}"
                schemas[pointer] = _schema_fingerprint(schema)

    info = document.get("info")
    info_fields: dict[str, object] = {}
    if isinstance(info, Mapping):
        for key in ("title", "version", "description"):
            value = info.get(key)
            if isinstance(value, str):
                info_fields[key] = value

    return {
        "operations": operations,
        "schemas": schemas,
        "info": info_fields,
        "openapi": _declared_version(document),
    }


def compare_surfaces(
    source: Mapping[str, Any],
    target: Mapping[str, Any],
    *,
    document_path: str,
) -> list[RawChange]:
    """Emit raw structural changes between two extracted surfaces."""
    changes: list[RawChange] = []
    src_ops = source["operations"] if isinstance(source.get("operations"), dict) else {}
    tgt_ops = target["operations"] if isinstance(target.get("operations"), dict) else {}
    src_schemas = source["schemas"] if isinstance(source.get("schemas"), dict) else {}
    tgt_schemas = target["schemas"] if isinstance(target.get("schemas"), dict) else {}
    src_info = source["info"] if isinstance(source.get("info"), dict) else {}
    tgt_info = target["info"] if isinstance(target.get("info"), dict) else {}

    for pointer in sorted(set(src_ops) - set(tgt_ops)):
        changes.append(
            RawChange(
                rule_id=RULE_PATH_REMOVE,
                kind="remove",
                location=pointer,
                location_kind="operation",
                evidence={
                    "document_path": document_path,
                    "before": src_ops[pointer],
                },
            )
        )
    for pointer in sorted(set(tgt_ops) - set(src_ops)):
        changes.append(
            RawChange(
                rule_id=RULE_PATH_ADD,
                kind="add",
                location=pointer,
                location_kind="operation",
                evidence={
                    "document_path": document_path,
                    "after": tgt_ops[pointer],
                },
            )
        )
    for pointer in sorted(set(src_ops) & set(tgt_ops)):
        if src_ops[pointer] != tgt_ops[pointer]:
            changes.append(
                RawChange(
                    rule_id=RULE_OPERATION_CHANGE,
                    kind="modify",
                    location=pointer,
                    location_kind="operation",
                    evidence={
                        "document_path": document_path,
                        "before": src_ops[pointer],
                        "after": tgt_ops[pointer],
                    },
                )
            )

    for pointer in sorted(set(src_schemas) - set(tgt_schemas)):
        changes.append(
            RawChange(
                rule_id=RULE_SCHEMA_REMOVE,
                kind="remove",
                location=pointer,
                location_kind="schema",
                evidence={
                    "document_path": document_path,
                    "before": src_schemas[pointer],
                },
            )
        )
    for pointer in sorted(set(tgt_schemas) - set(src_schemas)):
        changes.append(
            RawChange(
                rule_id=RULE_SCHEMA_ADD,
                kind="add",
                location=pointer,
                location_kind="schema",
                evidence={
                    "document_path": document_path,
                    "after": tgt_schemas[pointer],
                },
            )
        )
    for pointer in sorted(set(src_schemas) & set(tgt_schemas)):
        if src_schemas[pointer] != tgt_schemas[pointer]:
            changes.append(
                RawChange(
                    rule_id=RULE_SCHEMA_CHANGE,
                    kind="modify",
                    location=pointer,
                    location_kind="schema",
                    evidence={
                        "document_path": document_path,
                        "before": src_schemas[pointer],
                        "after": tgt_schemas[pointer],
                    },
                )
            )

    src_desc = src_info.get("description")
    tgt_desc = tgt_info.get("description")
    if src_desc != tgt_desc and (src_desc is not None or tgt_desc is not None):
        changes.append(
            RawChange(
                rule_id=RULE_INFO_DESCRIPTION,
                kind="modify",
                location="/info/description",
                location_kind="info",
                evidence={
                    "document_path": document_path,
                    "before": src_desc,
                    "after": tgt_desc,
                },
            )
        )

    return changes


def _declared_version(document: Mapping[str, Any]) -> str | None:
    openapi = document.get("openapi")
    if isinstance(openapi, str) and openapi.strip():
        return openapi.strip()
    swagger = document.get("swagger")
    if isinstance(swagger, str) and swagger.strip():
        return swagger.strip()
    return None


def _escape(segment: str) -> str:
    return segment.replace("~", "~0").replace("/", "~1")


def _operation_fingerprint(operation: object) -> dict[str, object]:
    if not isinstance(operation, Mapping):
        return {"malformed": True}
    body: dict[str, object] = {}
    op_id = operation.get("operationId")
    if isinstance(op_id, str):
        body["operationId"] = op_id
    responses = operation.get("responses")
    if isinstance(responses, Mapping):
        body["response_status"] = sorted(str(key) for key in responses)
    parameters = operation.get("parameters")
    if isinstance(parameters, list):
        body["parameter_count"] = len(parameters)
    request_body = operation.get("requestBody")
    body["has_request_body"] = isinstance(request_body, Mapping)
    return body


def _schema_fingerprint(schema: object) -> dict[str, object]:
    if not isinstance(schema, Mapping):
        return {"malformed": True}
    body: dict[str, object] = {}
    type_ = schema.get("type")
    if isinstance(type_, str):
        body["type"] = type_
    elif isinstance(type_, list):
        body["type"] = [str(item) for item in type_]
    required = schema.get("required")
    if isinstance(required, list):
        body["required"] = sorted(str(item) for item in required if isinstance(item, str))
    properties = schema.get("properties")
    if isinstance(properties, Mapping):
        body["properties"] = sorted(str(key) for key in properties)
    if schema.get("nullable") is True:
        body["nullable"] = True
    ref = schema.get("$ref")
    if isinstance(ref, str):
        body["$ref"] = ref
    return body
