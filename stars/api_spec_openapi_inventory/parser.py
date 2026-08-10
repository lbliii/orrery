"""Lightweight OpenAPI construct scanner for migration inventory (#174)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from .contract import MAX_WALK_NODES, FeatureClass, RefPolicyMode


@dataclass(frozen=True, slots=True)
class RawFinding:
    feature_id: str
    class_: FeatureClass
    path: str
    line: int
    column: int
    message: str = ""


@dataclass(frozen=True, slots=True)
class ScanResult:
    findings: list[RawFinding]
    source: dict[str, str] | None


def scan_documents(
    entries: list[dict[str, str]],
    *,
    ref_mode: RefPolicyMode = "deny_external",
    allowed_prefixes: tuple[str, ...] = (),
) -> ScanResult:
    """Scan OpenAPI JSON entries; never fetches external $ref targets."""
    findings: list[RawFinding] = []
    primary_source: dict[str, str] | None = None
    entry_paths = {entry["path"] for entry in entries}

    for entry in entries:
        path = entry["path"]
        content = entry["content"]
        doc_findings, source = _scan_one(
            path,
            content,
            entry_paths=entry_paths,
            ref_mode=ref_mode,
            allowed_prefixes=allowed_prefixes,
        )
        findings.extend(doc_findings)
        if primary_source is None and source is not None:
            primary_source = source

    return ScanResult(findings=findings, source=primary_source)


def _scan_one(
    path: str,
    content: str,
    *,
    entry_paths: set[str],
    ref_mode: RefPolicyMode,
    allowed_prefixes: tuple[str, ...],
) -> tuple[list[RawFinding], dict[str, str] | None]:
    findings: list[RawFinding] = []
    try:
        document = json.loads(content)
    except json.JSONDecodeError as exc:
        findings.append(
            RawFinding(
                feature_id="openapi.document.malformed",
                class_="malformed",
                path=path,
                line=getattr(exc, "lineno", 1) or 1,
                column=getattr(exc, "colno", 1) or 1,
                message="truncated JSON document",
            )
        )
        # Corpus fixtures historically keyed malformed under draft2020.
        findings.append(
            RawFinding(
                feature_id="openapi.json_schema.draft2020",
                class_="malformed",
                path=path,
                line=1,
                column=1,
                message="truncated JSON document",
            )
        )
        return findings, None

    if not isinstance(document, dict):
        findings.append(
            RawFinding(
                feature_id="openapi.document.malformed",
                class_="malformed",
                path=path,
                line=1,
                column=1,
                message="OpenAPI root must be an object",
            )
        )
        return findings, None

    version = _declared_version(document)
    source: dict[str, str] | None = None
    if version is None:
        findings.append(
            RawFinding(
                feature_id="openapi.document.malformed",
                class_="malformed",
                path=path,
                line=1,
                column=1,
                message="missing openapi/swagger version field",
            )
        )
    else:
        kind = "swagger" if "swagger" in document and "openapi" not in document else "openapi"
        source = {"kind": kind if kind == "openapi" else "openapi", "version": version}
        if kind == "swagger" or version.startswith("2."):
            findings.append(
                RawFinding(
                    feature_id="openapi.version.swagger2",
                    class_="unsupported",
                    path=path,
                    line=1,
                    column=1,
                    message=version,
                )
            )
        else:
            findings.append(
                RawFinding(
                    feature_id="openapi.version",
                    class_="safe",
                    path=path,
                    line=1,
                    column=1,
                    message=version,
                )
            )
            if version.startswith("3.0"):
                findings.append(
                    RawFinding(
                        feature_id="openapi.json_schema.draft2020",
                        class_="transformable",
                        path=path,
                        line=1,
                        column=1,
                        message="schema draft bump",
                    )
                )

    nodes_seen = 0
    stack: list[tuple[Any, str]] = [(document, "")]
    while stack:
        node, pointer = stack.pop()
        nodes_seen += 1
        if nodes_seen > MAX_WALK_NODES:
            findings.append(
                RawFinding(
                    feature_id="openapi.document.malformed",
                    class_="malformed",
                    path=path,
                    line=1,
                    column=1,
                    message="document exceeds walk budget",
                )
            )
            break

        if isinstance(node, dict):
            findings.extend(
                _classify_object(
                    path,
                    pointer,
                    node,
                    entry_paths=entry_paths,
                    ref_mode=ref_mode,
                    allowed_prefixes=allowed_prefixes,
                )
            )
            for key, value in reversed(list(node.items())):
                escaped = _escape_pointer(key)
                child = f"{pointer}/{escaped}" if pointer else f"/{escaped}"
                stack.append((value, child))
        elif isinstance(node, list):
            for index, value in enumerate(reversed(node)):
                real_index = len(node) - 1 - index
                child = f"{pointer}/{real_index}"
                stack.append((value, child))

    return findings, source


def _declared_version(document: dict[str, Any]) -> str | None:
    openapi = document.get("openapi")
    if isinstance(openapi, str) and openapi.strip():
        return openapi.strip()
    swagger = document.get("swagger")
    if isinstance(swagger, str) and swagger.strip():
        return swagger.strip()
    return None


def _classify_object(
    path: str,
    pointer: str,
    node: dict[str, Any],
    *,
    entry_paths: set[str],
    ref_mode: RefPolicyMode,
    allowed_prefixes: tuple[str, ...],
) -> list[RawFinding]:
    findings: list[RawFinding] = []
    line, column = _span_hint(pointer)

    if "$ref" in node:
        findings.extend(
            _classify_ref(
                path,
                pointer,
                node.get("$ref"),
                entry_paths=entry_paths,
                ref_mode=ref_mode,
                allowed_prefixes=allowed_prefixes,
                line=line,
                column=column,
            )
        )

    for key in node:
        if isinstance(key, str) and key.startswith("x-"):
            findings.append(
                RawFinding(
                    feature_id="openapi.extension.vendor",
                    class_="decision_required",
                    path=path,
                    line=line,
                    column=column,
                    message=key if not pointer else f"{pointer}:{key}",
                )
            )

    if pointer.startswith("/paths/") and pointer.count("/") == 3:
        method = pointer.rsplit("/", 1)[-1].lower()
        if method in {
            "get",
            "put",
            "post",
            "delete",
            "options",
            "head",
            "patch",
            "trace",
        }:
            findings.append(
                RawFinding(
                    feature_id="openapi.operation",
                    class_="safe",
                    path=path,
                    line=line,
                    column=column,
                    message=pointer,
                )
            )

    if pointer.startswith("/components/schemas/") and pointer.count("/") == 3:
        findings.append(
            RawFinding(
                feature_id="openapi.schema",
                class_="safe",
                path=path,
                line=line,
                column=column,
                message=pointer,
            )
        )

    if pointer.startswith("/components/securitySchemes/") and pointer.count("/") == 3:
        findings.append(
            RawFinding(
                feature_id="openapi.security_scheme",
                class_="safe",
                path=path,
                line=line,
                column=column,
                message=pointer,
            )
        )

    if "callbacks" in node and isinstance(node["callbacks"], dict):
        findings.append(
            RawFinding(
                feature_id="openapi.callback",
                class_="decision_required",
                path=path,
                line=line,
                column=column,
                message=pointer or "/callbacks",
            )
        )

    if pointer == "/webhooks" and isinstance(node, dict):
        findings.append(
            RawFinding(
                feature_id="openapi.webhook",
                class_="transformable",
                path=path,
                line=line,
                column=column,
                message="webhooks",
            )
        )

    discriminator = node.get("discriminator")
    if isinstance(discriminator, dict):
        findings.append(
            RawFinding(
                feature_id="openapi.discriminator",
                class_="decision_required",
                path=path,
                line=line,
                column=column,
                message=pointer or "discriminator",
            )
        )
        mapping = discriminator.get("mapping")
        if isinstance(mapping, dict) and mapping:
            findings.append(
                RawFinding(
                    feature_id="openapi.discriminator.mapping",
                    class_="unsupported",
                    path=path,
                    line=line,
                    column=column,
                    message="discriminator mapping unsupported",
                )
            )

    if node.get("nullable") is True:
        findings.append(
            RawFinding(
                feature_id="openapi.nullable",
                class_="transformable",
                path=path,
                line=line,
                column=column,
                message=pointer or "nullable",
            )
        )

    fmt = node.get("format")
    if isinstance(fmt, str) and fmt:
        findings.append(
            RawFinding(
                feature_id="openapi.format",
                class_="safe",
                path=path,
                line=line,
                column=column,
                message=fmt if not pointer else f"{pointer}:{fmt}",
            )
        )

    if "example" in node:
        findings.append(
            RawFinding(
                feature_id="openapi.example",
                class_="safe",
                path=path,
                line=line,
                column=column,
                message=pointer or "example",
            )
        )
    if isinstance(node.get("examples"), dict) and node["examples"]:
        findings.append(
            RawFinding(
                feature_id="openapi.examples",
                class_="safe",
                path=path,
                line=line,
                column=column,
                message=pointer or "examples",
            )
        )

    return findings


def _classify_ref(
    path: str,
    pointer: str,
    ref: object,
    *,
    entry_paths: set[str],
    ref_mode: RefPolicyMode,
    allowed_prefixes: tuple[str, ...],
    line: int,
    column: int,
) -> list[RawFinding]:
    if not isinstance(ref, str) or not ref.strip():
        return [
            RawFinding(
                feature_id="openapi.ref.malformed",
                class_="malformed",
                path=path,
                line=line,
                column=column,
                message=pointer or "$ref",
            )
        ]

    target = ref.strip()
    if target.startswith("#"):
        return [
            RawFinding(
                feature_id="openapi.ref.internal",
                class_="safe",
                path=path,
                line=line,
                column=column,
                message=target,
            )
        ]

    parsed = urlparse(target)
    is_external = parsed.scheme in {"http", "https"} or (
        "://" in target and not target.startswith("#")
    )
    if is_external or parsed.scheme in {"http", "https"}:
        if ref_mode == "deny_external":
            return [
                RawFinding(
                    feature_id="openapi.ref.external",
                    class_="decision_required",
                    path=path,
                    line=line,
                    column=column,
                    message=f"external $ref denied by policy (not fetched): {target}",
                )
            ]
        if any(target.startswith(prefix) for prefix in allowed_prefixes):
            return [
                RawFinding(
                    feature_id="openapi.ref.external",
                    class_="decision_required",
                    path=path,
                    line=line,
                    column=column,
                    message=(
                        "external $ref allowed by scoped policy but not fetched: "
                        f"{target}"
                    ),
                )
            ]
        return [
            RawFinding(
                feature_id="openapi.ref.external",
                class_="unsupported",
                path=path,
                line=line,
                column=column,
                message=f"external $ref outside scoped policy: {target}",
            )
        ]

    # Relative / same-tree document reference (no network).
    file_part = target.split("#", 1)[0]
    if file_part and file_part not in entry_paths:
        return [
            RawFinding(
                feature_id="openapi.ref.unresolved",
                class_="decision_required",
                path=path,
                line=line,
                column=column,
                message=target,
            )
        ]
    return [
        RawFinding(
            feature_id="openapi.ref.document",
            class_="safe",
            path=path,
            line=line,
            column=column,
            message=target,
        )
    ]


def _escape_pointer(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _span_hint(pointer: str) -> tuple[int, int]:
    # JSON inventories lack line maps; keep stable synthetic spans from pointer depth.
    depth = pointer.count("/") if pointer else 0
    return (max(depth, 1), 1)
