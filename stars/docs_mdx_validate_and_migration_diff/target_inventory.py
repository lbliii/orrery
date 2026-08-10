"""Inventory constructs present in generated MDX/Markdown targets."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from stars.docs_myst_inventory.contract import ADMONITION_DIRECTIVES
from stars.docs_myst_inventory.parser import RawFinding, scan_document

_ADMONITION_OPEN_RE = re.compile(
    r'<Admonition\s+type="([A-Za-z0-9_-]+)"(?:\s+title="([^"]*)")?\s*>'
)
_HEADING_RE = re.compile(r"^(#{1,6})\s+\S", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class ConstructCount:
    feature_id: str
    path: str
    count: int


def inventory_targets(
    entries: Sequence[Mapping[str, str]],
) -> dict[str, object]:
    """Build a bounded target inventory of MDX/MyST constructs per path."""
    findings: list[RawFinding] = []
    counts: list[ConstructCount] = []

    for entry in entries:
        path = entry["path"]
        content = entry["content"]
        # Residual MyST / markdown constructs via source scanner.
        findings.extend(scan_document(path, content))

        heading_n = len(_HEADING_RE.findall(content))
        if heading_n:
            counts.append(ConstructCount("md.heading", path, heading_n))

        admonition_n = len(_ADMONITION_OPEN_RE.findall(content))
        if admonition_n:
            counts.append(
                ConstructCount("mdx.component.admonition", path, admonition_n)
            )
            for match in _ADMONITION_OPEN_RE.finditer(content):
                line = content.count("\n", 0, match.start()) + 1
                column = match.start() - content.rfind("\n", 0, match.start())
                findings.append(
                    RawFinding(
                        feature_id="mdx.component.admonition",
                        class_="safe",
                        path=path,
                        line=line,
                        column=max(column, 1),
                        message=match.group(1),
                    )
                )

        residual = 0
        for match in re.finditer(
            r"```\{([A-Za-z0-9_.-]+)\}|:::\s*\{([A-Za-z0-9_.-]+)\}", content
        ):
            name = (match.group(1) or match.group(2) or "").lower()
            if name in ADMONITION_DIRECTIVES:
                residual += 1
        if residual:
            counts.append(
                ConstructCount("myst.directive.admonition", path, residual)
            )

    feature_rows = [
        {"feature_id": row.feature_id, "path": row.path, "count": row.count}
        for row in sorted(counts, key=lambda item: (item.path, item.feature_id))
    ]
    return {
        "findings": findings,
        "constructs": feature_rows,
        "entry_count": len(entries),
        "finding_count": len(findings),
    }
