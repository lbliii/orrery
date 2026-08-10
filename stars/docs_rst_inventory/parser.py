"""Lightweight reStructuredText/Sphinx construct scanner for migration inventory."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .contract import (
    ADMONITION_DIRECTIVES,
    AUTODOC_DIRECTIVES,
    SAFE_DIRECTIVES,
    TABLE_DIRECTIVES,
    TRANSFORMABLE_ROLES,
    FeatureClass,
)

_DIRECTIVE_RE = re.compile(r"^\.\.\s+([A-Za-z0-9_.+-]+)::\s*(.*)$")
_SUBST_DEF_RE = re.compile(r"^\.\.\s+\|([^|]+)\|\s+([A-Za-z0-9_.+-]+)::\s*(.*)$")
_ROLE_RE = re.compile(r":([A-Za-z0-9_.+-]+):`([^`]*)`")
_SUBST_REF_RE = re.compile(r"(?<!\\)\|([A-Za-z0-9_.+-]+)\|")
_UNDERLINE_RE = re.compile(r'^([=\-~^"\'`#*+])\1{2,}\s*$')
_EXPLICIT_TARGET_RE = re.compile(r"^\.\.\s+_([A-Za-z0-9_.:+-]+):\s*(.*)$")
_RAW_MALFORMED_RE = re.compile(r"^\.\.\s*$")
_GRID_TABLE_RE = re.compile(r"^\+[-=+]+\+\s*$")
_SIMPLE_TABLE_RE = re.compile(r"^={3,}(\s+={3,})+\s*$")


@dataclass(frozen=True, slots=True)
class RawFinding:
    feature_id: str
    class_: FeatureClass
    path: str
    line: int
    column: int
    message: str = ""


def scan_document(path: str, content: str) -> list[RawFinding]:
    """Scan one RST document and return ordered raw findings."""
    normalized = content.replace("\r\n", "\n")
    lines = normalized.split("\n")
    findings: list[RawFinding] = []

    for line_no, line in enumerate(lines, start=1):
        findings.extend(_scan_heading(path, lines, line_no))
        findings.extend(_scan_tables(path, line, line_no))
        findings.extend(_scan_directive_or_target(path, line, line_no))
        findings.extend(_scan_roles(path, line, line_no))
        findings.extend(_scan_substitution_refs(path, line, line_no))

        if _RAW_MALFORMED_RE.match(line):
            findings.append(
                RawFinding(
                    feature_id="rst.directive.malformed",
                    class_="malformed",
                    path=path,
                    line=line_no,
                    column=1,
                    message="orphan ellipsis without directive",
                )
            )

    return findings


def _scan_heading(path: str, lines: list[str], line_no: int) -> list[RawFinding]:
    if line_no >= len(lines):
        return []
    title = lines[line_no - 1]
    underline = lines[line_no]
    if not title.strip() or not _UNDERLINE_RE.match(underline):
        return []
    if len(underline.strip()) < len(title.strip()):
        return []
    # Avoid treating grid-table separators as section underlines.
    if underline.lstrip().startswith("+"):
        return []
    return [
        RawFinding(
            feature_id="rst.heading",
            class_="safe",
            path=path,
            line=line_no,
            column=1,
            message=title.strip()[:120],
        )
    ]


def _scan_tables(path: str, line: str, line_no: int) -> list[RawFinding]:
    if _GRID_TABLE_RE.match(line) or _SIMPLE_TABLE_RE.match(line):
        return [
            RawFinding(
                feature_id="rst.table.markup",
                class_="decision_required",
                path=path,
                line=line_no,
                column=1,
                message="inline table markup",
            )
        ]
    return []


def _scan_directive_or_target(path: str, line: str, line_no: int) -> list[RawFinding]:
    findings: list[RawFinding] = []
    subst = _SUBST_DEF_RE.match(line)
    if subst:
        name = subst.group(1)
        findings.append(
            RawFinding(
                feature_id="rst.substitution.definition",
                class_="decision_required",
                path=path,
                line=line_no,
                column=line.find("|") + 1,
                message=name,
            )
        )
        return findings

    target = _EXPLICIT_TARGET_RE.match(line)
    if target:
        findings.append(
            RawFinding(
                feature_id="rst.target.explicit",
                class_="safe",
                path=path,
                line=line_no,
                column=1,
                message=target.group(1),
            )
        )
        return findings

    match = _DIRECTIVE_RE.match(line)
    if not match:
        return findings

    directive = match.group(1)
    args = (match.group(2) or "").strip()
    feature_id, class_ = _classify_directive(directive)
    findings.append(
        RawFinding(
            feature_id=feature_id,
            class_=class_,
            path=path,
            line=line_no,
            column=line.find("..") + 1,
            message=_directive_message(directive, args),
        )
    )
    if args and directive.lower() == "include":
        findings.append(
            RawFinding(
                feature_id="rst.ref.include",
                class_="decision_required",
                path=path,
                line=line_no,
                column=line.find(args) + 1,
                message=args,
            )
        )
    if args and directive.lower() in {"image", "figure"}:
        findings.append(
            RawFinding(
                feature_id="rst.asset.image",
                class_="safe",
                path=path,
                line=line_no,
                column=line.find(args) + 1,
                message=args,
            )
        )
    return findings


def _scan_roles(path: str, line: str, line_no: int) -> list[RawFinding]:
    findings: list[RawFinding] = []
    for match in _ROLE_RE.finditer(line):
        role = match.group(1)
        feature_id, class_ = _classify_role(role)
        findings.append(
            RawFinding(
                feature_id=feature_id,
                class_=class_,
                path=path,
                line=line_no,
                column=match.start() + 1,
                message=match.group(2),
            )
        )
    return findings


def _scan_substitution_refs(path: str, line: str, line_no: int) -> list[RawFinding]:
    if line.lstrip().startswith(".."):
        return []
    findings: list[RawFinding] = []
    for match in _SUBST_REF_RE.finditer(line):
        findings.append(
            RawFinding(
                feature_id="rst.substitution.reference",
                class_="decision_required",
                path=path,
                line=line_no,
                column=match.start() + 1,
                message=match.group(1),
            )
        )
    return findings


def _classify_directive(name: str) -> tuple[str, FeatureClass]:
    lowered = name.lower()
    if lowered in ADMONITION_DIRECTIVES:
        return "rst.directive.admonition", "transformable"
    if lowered == "include":
        return "rst.directive.include", "decision_required"
    if lowered == "toctree":
        return "rst.directive.toctree", "decision_required"
    if lowered in AUTODOC_DIRECTIVES:
        return f"rst.directive.{lowered}", "unsupported"
    if lowered == "raw":
        return "rst.directive.raw", "unsupported"
    if lowered in TABLE_DIRECTIVES:
        return "rst.directive.table", "decision_required"
    if lowered in {"math", "math-block"}:
        return "rst.directive.math", "decision_required"
    if lowered in SAFE_DIRECTIVES:
        if lowered in {"image", "figure"}:
            return f"rst.directive.{lowered}", "safe"
        return f"rst.directive.{lowered}", "safe"
    # Unknown / custom Sphinx extensions — not eligible for automatic mapping.
    return f"rst.directive.{lowered}", "unsupported"


def _classify_role(name: str) -> tuple[str, FeatureClass]:
    lowered = name.lower()
    if lowered in TRANSFORMABLE_ROLES:
        return f"rst.role.{lowered}", "transformable"
    if lowered == "math":
        return "rst.role.math", "decision_required"
    if lowered in {"class", "func", "mod", "meth", "attr", "exc", "data", "obj"}:
        return f"rst.role.{lowered}", "unsupported"
    return f"rst.role.{lowered}", "unsupported"


def _directive_message(directive: str, args: str) -> str:
    if args:
        return f"{directive} {args}".strip()
    return directive
