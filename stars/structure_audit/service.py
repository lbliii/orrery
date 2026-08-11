"""Pure structure audit over caller-supplied markdown file sets."""

from __future__ import annotations

import re
from collections.abc import Mapping

from .contract import MAX_CONTENT_BYTES, MAX_FILES, MAX_FINDINGS, MAX_PATH_LEN

_PATH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(\S.*)$", re.MULTILINE)
_MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
_FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)

# Advisory fix text for agents — does not change pass/fail or codes.
_REMEDIATION: dict[str, str] = {
    "empty_file": (
        "Add non-empty markdown content to this file, or remove it from the bundle."
    ),
    "frontmatter_invalid": (
        "Fix the YAML frontmatter fence: open with --- on its own line, "
        "close with --- on its own line, then the document body."
    ),
    "frontmatter_missing_title": (
        "Add a `title:` key to the YAML frontmatter block."
    ),
    "missing_h1": (
        "Ensure the document body (after frontmatter) starts with a single "
        "`#` H1 heading."
    ),
    "heading_level_skip": (
        "Insert intermediate heading levels so heading depth increases by "
        "at most one at a time (for example, add an h2 before an h3)."
    ),
    "orphan_file": (
        "Add a relative markdown link to this file from another file in the "
        "set, or rename it to index.md/readme.md if it is an entry point."
    ),
}


def _finding(
    code: str,
    path: str,
    message: str,
    **extra: object,
) -> dict[str, object]:
    item: dict[str, object] = {
        "code": code,
        "path": path,
        "message": message,
        "remediation": _REMEDIATION[code],
    }
    item.update(extra)
    return item


def audit(files: object) -> dict[str, object]:
    """Emit coded findings for heading gaps, frontmatter errors, and orphans."""
    parsed, error = _parse_files(files)
    if error is not None:
        return error
    assert parsed is not None

    findings: list[dict[str, object]] = []
    path_set = {entry["path"] for entry in parsed}
    inbound: dict[str, int] = {path: 0 for path in path_set}

    for entry in parsed:
        path = entry["path"]
        content = entry["content"]
        if not content.strip():
            findings.append(
                _finding("empty_file", path, "file content is empty")
            )

        findings.extend(_frontmatter_findings(path, content))
        findings.extend(_heading_findings(path, content))

        for target in _local_targets(content):
            if target in inbound:
                inbound[target] += 1
            elif target in path_set:
                inbound[target] = inbound.get(target, 0) + 1

    if len(parsed) > 1:
        for path, count in sorted(inbound.items()):
            if count == 0 and not _is_index(path):
                findings.append(
                    _finding(
                        "orphan_file",
                        path,
                        "no inbound relative markdown links",
                    )
                )

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
        "file_count": len(parsed),
        "passed": not findings,
    }


def _parse_files(
    files: object,
) -> tuple[list[dict[str, str]] | None, dict[str, object] | None]:
    if not isinstance(files, list) or not files or len(files) > MAX_FILES:
        return None, {"error": "files_invalid"}

    parsed: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, raw in enumerate(files):
        if not isinstance(raw, Mapping):
            return None, {"error": "entry_not_object", "index": index}
        if set(raw) - {"path", "content"}:
            return None, {"error": "entry_unknown_fields", "index": index}
        path = raw.get("path")
        content = raw.get("content")
        if not isinstance(path, str) or not path or len(path) > MAX_PATH_LEN:
            return None, {"error": "path_invalid", "index": index}
        if not path.endswith(".md"):
            return None, {"error": "path_not_markdown", "path": path, "index": index}
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


def _frontmatter_findings(path: str, content: str) -> list[dict[str, object]]:
    match = _FRONTMATTER_RE.match(content)
    if match is None:
        if content.lstrip().startswith("---"):
            return [
                _finding(
                    "frontmatter_invalid",
                    path,
                    "frontmatter fence is malformed",
                )
            ]
        return []

    body = match.group(1)
    if "title:" not in body:
        return [
            _finding(
                "frontmatter_missing_title",
                path,
                "YAML frontmatter lacks title",
            )
        ]
    return []


def _heading_findings(path: str, content: str) -> list[dict[str, object]]:
    body = content
    fm = _FRONTMATTER_RE.match(content)
    if fm is not None:
        body = content[fm.end() :]

    headings = [(len(hashes), title.strip()) for hashes, title in _HEADING_RE.findall(body)]
    findings: list[dict[str, object]] = []
    if not headings:
        findings.append(
            _finding("missing_h1", path, "no markdown headings found")
        )
        return findings

    if headings[0][0] != 1:
        findings.append(
            _finding(
                "missing_h1",
                path,
                "document does not start with an H1",
            )
        )

    previous = headings[0][0]
    for level, _title in headings[1:]:
        if level > previous + 1:
            findings.append(
                _finding(
                    "heading_level_skip",
                    path,
                    f"heading jumps from h{previous} to h{level}",
                    from_level=previous,
                    to_level=level,
                )
            )
        previous = level
    return findings


def _local_targets(content: str) -> list[str]:
    targets: list[str] = []
    for raw in _MD_LINK_RE.findall(content):
        target = raw.strip()
        if not target or target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target = target.split("#", 1)[0].split("?", 1)[0]
        if target.endswith(".md"):
            targets.append(target)
    return targets


def _is_index(path: str) -> bool:
    name = path.rsplit("/", 1)[-1].lower()
    return name in {"index.md", "readme.md"}
