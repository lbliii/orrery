"""Pure Kida static validation over caller-supplied template bundles."""

from __future__ import annotations

import re
import tempfile
from collections.abc import Mapping
from pathlib import Path

from kida._check import collect_check_diagnostics
from kida.diagnostics import Diagnostic

from .contract import (
    ALLOWED_SUFFIXES,
    MAX_CONTENT_BYTES,
    MAX_FINDINGS,
    MAX_PATH_LEN,
    MAX_TEMPLATES,
)

_PATH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")


def check(
    templates: object,
    *,
    validate_calls: bool = True,
    strict: bool = False,
) -> dict[str, object]:
    """Validate Kida templates and emit coded findings (no render)."""
    parsed, error = _parse_templates(templates)
    if error is not None:
        return error
    assert parsed is not None

    with tempfile.TemporaryDirectory(prefix="orrery-kida-check-") as tmp:
        root = Path(tmp)
        for entry in parsed:
            path = root / entry["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(entry["content"], encoding="utf-8")

        result = collect_check_diagnostics(
            root,
            strict=strict,
            validate_calls=validate_calls,
            a11y=False,
            typed=False,
            lint_fragile_paths=False,
        )

    findings = [_finding_from_diagnostic(item) for item in result.diagnostics]
    findings.sort(key=lambda item: (str(item["code"]), str(item["path"])))
    truncated = len(findings) > MAX_FINDINGS
    if truncated:
        findings = findings[:MAX_FINDINGS]

    codes = sorted({str(item["code"]) for item in findings})
    return {
        "findings": findings,
        "finding_codes": codes,
        "finding_count": len(findings),
        "findings_truncated": truncated,
        "template_count": len(parsed),
        "passed": result.exit_code == 0,
        "partial": result.partial,
        "validate_calls": validate_calls,
        "strict": strict,
    }


def _finding_from_diagnostic(diagnostic: Diagnostic) -> dict[str, object]:
    line = None
    column = None
    if diagnostic.span.start is not None:
        line = diagnostic.span.start.line
        column = diagnostic.span.start.column

    return {
        "code": diagnostic.code,
        "path": diagnostic.span.path or "",
        "message": diagnostic.message,
        "severity": diagnostic.severity.value,
        "category": diagnostic.category,
        "line": line,
        "column": column,
        "suggestion": diagnostic.suggestion,
    }


def _parse_templates(
    templates: object,
) -> tuple[list[dict[str, str]] | None, dict[str, object] | None]:
    if not isinstance(templates, list) or not templates or len(templates) > MAX_TEMPLATES:
        return None, {"error": "templates_invalid"}

    parsed: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, raw in enumerate(templates):
        if not isinstance(raw, Mapping):
            return None, {"error": "entry_not_object", "index": index}
        if set(raw) - {"path", "content"}:
            return None, {"error": "entry_unknown_fields", "index": index}
        path = raw.get("path")
        content = raw.get("content")
        if not isinstance(path, str) or not path or len(path) > MAX_PATH_LEN:
            return None, {"error": "path_invalid", "index": index}
        if not path.endswith(ALLOWED_SUFFIXES):
            return None, {
                "error": "path_not_template",
                "path": path,
                "index": index,
            }
        if path.startswith("/") or path.startswith("../") or "/../" in f"/{path}/":
            return None, {"error": "path_traversal", "path": path, "index": index}
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
