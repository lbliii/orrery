"""Pinned MDX target build/lint adapter for docs migration validation."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from stars.docs_myst_inventory.contract import ADMONITION_DIRECTIVES

_ADMONITION_OPEN_RE = re.compile(
    r'<Admonition\s+type="([A-Za-z0-9_-]+)"(?:\s+title="([^"]*)")?\s*>'
)
_ADMONITION_CLOSE = "</Admonition>"
_RESIDUAL_DIRECTIVE_RE = re.compile(
    r"```\{([A-Za-z0-9_.-]+)\}|:::\s*\{([A-Za-z0-9_.-]+)\}"
)
_SELF_CLOSING_RE = re.compile(r"<([A-Za-z][A-Za-z0-9]*)\b[^>]*/\s*>")


def check_mdx_buildable(targets: Sequence[Mapping[str, str]]) -> dict[str, object]:
    """Deterministic MDX syntax/build checks for migration targets.

    This adapter proves target conformance for the baseline MDX profile. It
    does **not** claim runtime/framework compatibility (Docusaurus, Starlight).
    """
    findings: list[dict[str, object]] = []
    for entry in targets:
        path = str(entry["path"])
        content = str(entry["content"])
        if not content.strip():
            findings.append(
                {
                    "feature_id": "mdx.empty",
                    "class": "malformed",
                    "path": path,
                    "severity": "breaking",
                    "action": "block",
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
                    "severity": "breaking",
                    "action": "block",
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
                        "severity": "breaking",
                        "action": "block",
                        "message": f"unconverted admonition fence {{{name}}}",
                    }
                )

        tag_findings = _jsx_balance_findings(path, content)
        findings.extend(tag_findings)

    return {
        "passed": not findings,
        "findings": findings,
        "validator": {
            "name": "orrery/docs-mdx-validate",
            "version": "1.0.0",
        },
    }


def _jsx_balance_findings(path: str, content: str) -> list[dict[str, object]]:
    """Detect grossly unbalanced non-void JSX open/close tags (Admonition+)."""
    stack: list[str] = []
    findings: list[dict[str, object]] = []
    # Strip fenced code so code samples with HTML do not trip the checker.
    scrubbed = _strip_fenced_code(content)

    for match in re.finditer(
        r"<(/)?([A-Za-z][A-Za-z0-9]*)\b[^>]*/?>", scrubbed
    ):
        full = match.group(0)
        closing = match.group(1) == "/"
        name = match.group(2)
        if name[0].islower():
            # HTML-ish tags are out of scope for this adapter.
            continue
        if full.rstrip().endswith("/>") or _SELF_CLOSING_RE.fullmatch(full):
            continue
        if closing:
            if not stack or stack[-1] != name:
                findings.append(
                    {
                        "feature_id": "mdx.jsx.unbalanced",
                        "class": "malformed",
                        "path": path,
                        "severity": "breaking",
                        "action": "block",
                        "message": f"unexpected close </{name}>",
                    }
                )
            else:
                stack.pop()
        else:
            stack.append(name)

    for name in stack:
        findings.append(
            {
                "feature_id": "mdx.jsx.unbalanced",
                "class": "malformed",
                "path": path,
                "severity": "breaking",
                "action": "block",
                "message": f"unclosed <{name}>",
            }
        )
    return findings


def _strip_fenced_code(content: str) -> str:
    lines = content.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    in_fence = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else line)
    return "\n".join(out)
