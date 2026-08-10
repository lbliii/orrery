"""Lightweight MyST/Markdown construct scanner for migration inventory."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .contract import ADMONITION_DIRECTIVES, FeatureClass

_HEADING_RE = re.compile(r"^(#{1,6})\s+\S")
_LINK_RE = re.compile(r"(!?\[[^\]]*\])\(([^)]+)\)")
_ROLE_RE = re.compile(r"\{([A-Za-z0-9_.-]+)\}`([^`]*)`")
_FENCE_OPEN_RE = re.compile(r"^(`{3,})\{([^}\s]+)\}(?:\s+(.+))?\s*$")
_PLAIN_FENCE_RE = re.compile(r"^(`{3,})(\s*\w*)?\s*$")
_COLON_OPEN_RE = re.compile(r"^:::\s*\{([^}\s]+)\}(?:\s+(.+))?\s*$")
_COLON_CLOSE_RE = re.compile(r"^:::\s*$")


@dataclass(frozen=True, slots=True)
class RawFinding:
    feature_id: str
    class_: FeatureClass
    path: str
    line: int
    column: int
    message: str = ""


def scan_document(path: str, content: str) -> list[RawFinding]:
    """Scan one MyST/Markdown document and return ordered raw findings."""
    normalized = content.replace("\r\n", "\n")
    lines = normalized.split("\n")
    findings: list[RawFinding] = []
    in_fence = False
    fence_start_line = 0
    colon_depth = 0
    colon_stack: list[tuple[int, str, str]] = []

    for line_no, line in enumerate(lines, start=1):
        if not in_fence and colon_depth == 0:
            findings.extend(_scan_headings(path, line, line_no))
            findings.extend(_scan_links_and_assets(path, line, line_no))
            findings.extend(_scan_roles(path, line, line_no))

        colon_match = _COLON_OPEN_RE.match(line.strip())
        if colon_match and not in_fence:
            directive = colon_match.group(1)
            args = (colon_match.group(2) or "").strip()
            feature_id, class_ = _classify_directive(directive)
            findings.append(
                RawFinding(
                    feature_id=feature_id,
                    class_=class_,
                    path=path,
                    line=line_no,
                    column=line.find(":::") + 1,
                    message=_directive_message(directive, args),
                )
            )
            if args and directive == "include":
                findings.append(
                    RawFinding(
                        feature_id="myst.ref.include",
                        class_="decision_required",
                        path=path,
                        line=line_no,
                        column=line.find(args) + 1,
                        message=args,
                    )
                )
            colon_stack.append((line_no, directive, args))
            colon_depth += 1
            continue

        if _COLON_CLOSE_RE.match(line.strip()) and not in_fence:
            if colon_depth == 0:
                findings.append(
                    RawFinding(
                        feature_id="myst.directive.malformed",
                        class_="malformed",
                        path=path,
                        line=line_no,
                        column=line.find(":::") + 1,
                        message="unexpected closing colon fence",
                    )
                )
            else:
                colon_stack.pop()
                colon_depth -= 1
            continue

        fence_match = _FENCE_OPEN_RE.match(line.strip())
        if fence_match and not in_fence and colon_depth == 0:
            directive = fence_match.group(2)
            args = (fence_match.group(3) or "").strip()
            feature_id, class_ = _classify_directive(directive)
            findings.append(
                RawFinding(
                    feature_id=feature_id,
                    class_=class_,
                    path=path,
                    line=line_no,
                    column=line.find("{") + 1,
                    message=_directive_message(directive, args),
                )
            )
            if args and directive == "include":
                findings.append(
                    RawFinding(
                        feature_id="myst.ref.include",
                        class_="decision_required",
                        path=path,
                        line=line_no,
                        column=line.find(args) + 1,
                        message=args,
                    )
                )
            in_fence = True
            fence_start_line = line_no
            continue

        plain_fence = _PLAIN_FENCE_RE.match(line.strip())
        if plain_fence and colon_depth == 0:
            if in_fence:
                in_fence = False
            elif plain_fence.group(2) and plain_fence.group(2).strip():
                lang = plain_fence.group(2).strip()
                findings.append(
                    RawFinding(
                        feature_id="md.fenced_code",
                        class_="safe",
                        path=path,
                        line=line_no,
                        column=line.find("`") + 1,
                        message=lang,
                    )
                )
                in_fence = True
                fence_start_line = line_no
            else:
                if line.strip().startswith("```{"):
                    findings.append(
                        RawFinding(
                            feature_id="myst.directive.malformed",
                            class_="malformed",
                            path=path,
                            line=line_no,
                            column=line.find("`") + 1,
                            message="invalid fenced directive opener",
                        )
                    )
                elif not in_fence:
                    findings.append(
                        RawFinding(
                            feature_id="md.fenced_code",
                            class_="safe",
                            path=path,
                            line=line_no,
                            column=line.find("`") + 1,
                        )
                    )
                    in_fence = True
                    fence_start_line = line_no
                else:
                    in_fence = False
            continue

    if in_fence:
        findings.append(
            RawFinding(
                feature_id="myst.directive.malformed",
                class_="malformed",
                path=path,
                line=fence_start_line,
                column=1,
                message="unclosed fenced block",
            )
        )
    if colon_depth:
        start_line, directive, _ = colon_stack[0]
        findings.append(
            RawFinding(
                feature_id="myst.directive.malformed",
                class_="malformed",
                path=path,
                line=start_line,
                column=1,
                message=f"unclosed colon fence for {directive}",
            )
        )
    return findings


def _scan_headings(path: str, line: str, line_no: int) -> list[RawFinding]:
    match = _HEADING_RE.match(line)
    if not match:
        return []
    return [
        RawFinding(
            feature_id="md.heading",
            class_="safe",
            path=path,
            line=line_no,
            column=line.find("#") + 1,
        )
    ]


def _scan_links_and_assets(path: str, line: str, line_no: int) -> list[RawFinding]:
    findings: list[RawFinding] = []
    for match in _LINK_RE.finditer(line):
        target = match.group(2).strip()
        column = match.start() + 1
        if match.group(1).startswith("!"):
            findings.append(
                RawFinding(
                    feature_id="myst.asset.image",
                    class_="safe",
                    path=path,
                    line=line_no,
                    column=column,
                    message=target,
                )
            )
        else:
            findings.append(
                RawFinding(
                    feature_id="md.link",
                    class_="safe",
                    path=path,
                    line=line_no,
                    column=column,
                    message=target,
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


def _classify_directive(name: str) -> tuple[str, FeatureClass]:
    lowered = name.lower()
    if lowered in ADMONITION_DIRECTIVES:
        return "myst.directive.admonition", "transformable"
    if lowered == "include":
        return "myst.directive.include", "decision_required"
    if lowered in {"toctree", "tableofcontents"}:
        return "myst.directive.toctree", "decision_required"
    return f"myst.directive.{lowered}", "unsupported"


def _classify_role(name: str) -> tuple[str, FeatureClass]:
    lowered = name.lower()
    if lowered in {"ref", "doc", "term", "abbr"}:
        return f"myst.role.{lowered}", "transformable"
    if lowered == "math":
        return "myst.role.math", "decision_required"
    return f"myst.role.{lowered}", "unsupported"


def _directive_message(directive: str, args: str) -> str:
    if args:
        return f"{directive} {args}".strip()
    return directive
