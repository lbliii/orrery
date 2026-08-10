"""Safe MyST → baseline MDX transforms for the corpus-backed subset."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from stars.docs_myst_inventory.contract import ADMONITION_DIRECTIVES

_FENCE_ADMONITION_RE = re.compile(
    r"^(`{3,})\{("
    + "|".join(sorted(ADMONITION_DIRECTIVES, key=len, reverse=True))
    + r")\}(?:\s+(.+))?\s*$"
)
_COLON_ADMONITION_RE = re.compile(
    r"^:::\s*\{("
    + "|".join(sorted(ADMONITION_DIRECTIVES, key=len, reverse=True))
    + r")\}(?:\s+(.+))?\s*$"
)
_COLON_CLOSE_RE = re.compile(r"^:::\s*$")
_PLAIN_FENCE_CLOSE_RE = re.compile(r"^(`{3,})\s*$")
_RESIDUAL_DIRECTIVE_RE = re.compile(
    r"```\{([A-Za-z0-9_.-]+)\}|:::\s*\{([A-Za-z0-9_.-]+)\}"
)
_ADMONITION_OPEN_RE = re.compile(
    r'<Admonition\s+type="([A-Za-z0-9_-]+)"(?:\s+title="([^"]*)")?\s*>'
)
_ADMONITION_CLOSE = "</Admonition>"


def transform_document(content: str, *, allow_admonition: bool) -> str:
    """Transform one document, preserving unsupported directive source text."""
    normalized = content.replace("\r\n", "\n")
    if not allow_admonition:
        return normalized

    lines = normalized.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        fence = _FENCE_ADMONITION_RE.match(line.strip())
        if fence:
            marker = fence.group(1)
            kind = fence.group(2).lower()
            title = (fence.group(3) or "").strip()
            body, i = _collect_fence_body(lines, i + 1, marker)
            out.append(_admonition_open(kind, title))
            out.extend(body)
            out.append(_ADMONITION_CLOSE)
            continue

        colon = _COLON_ADMONITION_RE.match(line.strip())
        if colon:
            kind = colon.group(1).lower()
            title = (colon.group(2) or "").strip()
            body, i = _collect_colon_body(lines, i + 1)
            out.append(_admonition_open(kind, title))
            out.extend(body)
            out.append(_ADMONITION_CLOSE)
            continue

        out.append(line)
        i += 1
    return "\n".join(out)


def baseline_mdx_buildable(targets: Sequence[Mapping[str, str]]) -> dict[str, object]:
    """Lightweight baseline MDX check used until docs/mdx-validate (#172) ships.

    Safe corpus outputs must keep headings, emit balanced Admonition tags when
    present, and not leave corpus admonition fences unconverted.
    """
    findings: list[dict[str, object]] = []
    for entry in targets:
        path = entry["path"]
        content = entry["content"]
        if not content.strip():
            findings.append(
                {
                    "feature_id": "mdx.empty",
                    "class": "malformed",
                    "path": path,
                    "message": "empty target",
                }
            )
            continue

        open_count = len(_ADMONITION_OPEN_RE.findall(content))
        close_count = content.count(_ADMONITION_CLOSE)
        if open_count != close_count:
            findings.append(
                {
                    "feature_id": "mdx.admonition.unbalanced",
                    "class": "malformed",
                    "path": path,
                    "message": f"open={open_count} close={close_count}",
                }
            )

        for match in _RESIDUAL_DIRECTIVE_RE.finditer(content):
            name = (match.group(1) or match.group(2) or "").lower()
            if name in ADMONITION_DIRECTIVES:
                findings.append(
                    {
                        "feature_id": "myst.directive.admonition",
                        "class": "malformed",
                        "path": path,
                        "message": f"unconverted admonition fence {{{name}}}",
                    }
                )

    return {
        "passed": not findings,
        "findings": findings,
        "validator": {
            "name": "orrery/docs-mdx-validate-baseline-stub",
            "version": "0.1.0",
        },
    }


def _admonition_open(kind: str, title: str) -> str:
    if title:
        escaped = title.replace('"', "&quot;")
        return f'<Admonition type="{kind}" title="{escaped}">'
    return f'<Admonition type="{kind}">'


def _collect_fence_body(lines: list[str], start: int, marker: str) -> tuple[list[str], int]:
    body: list[str] = []
    i = start
    close = re.compile(rf"^{re.escape(marker)}\s*$")
    while i < len(lines):
        if close.match(lines[i].strip()) or _PLAIN_FENCE_CLOSE_RE.match(lines[i].strip()):
            return body, i + 1
        body.append(lines[i])
        i += 1
    return body, i


def _collect_colon_body(lines: list[str], start: int) -> tuple[list[str], int]:
    body: list[str] = []
    i = start
    while i < len(lines):
        if _COLON_CLOSE_RE.match(lines[i].strip()):
            return body, i + 1
        body.append(lines[i])
        i += 1
    return body, i
