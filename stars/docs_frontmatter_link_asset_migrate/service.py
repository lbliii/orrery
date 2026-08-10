"""Rewrite frontmatter, links, anchors, and assets under explicit rules."""

from __future__ import annotations

import difflib
import hashlib
import posixpath
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from .contract import (
    DEFAULT_SUPPORTED_ASSET_EXTENSIONS,
    EXECUTION_GRANTS,
    MAX_ENTRIES,
    MAX_ENTRY_BYTES,
    MAX_FINDINGS,
    MAX_MESSAGE_BYTES,
    MAX_PATCH_BYTES,
    MAX_PATH_LEN,
    MAX_RULE_MAP_ENTRIES,
    FeatureClass,
)

_PATH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
_FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?", re.DOTALL)
_LINK_RE = re.compile(r"(!?\[[^\]]*\])\(([^)]+)\)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
_FM_LINE_RE = re.compile(r"^(\s*)([A-Za-z0-9_.-]+)(\s*:\s*)(.*)$")


@dataclass(frozen=True, slots=True)
class ParsedRules:
    field_renames: dict[str, str]
    path_redirects: dict[str, str]
    anchor_redirects: dict[str, str]
    supported_asset_extensions: frozenset[str]
    execution_grants: frozenset[str]


@dataclass(frozen=True, slots=True)
class RawFinding:
    feature_id: str
    class_: FeatureClass
    path: str
    line: int
    column: int
    message: str = ""


def migrate(
    entries: Sequence[Mapping[str, Any]] | None = None,
    rules: Mapping[str, Any] | None = None,
) -> dict[str, object]:
    """Migrate frontmatter/links/assets and emit a patch plus report."""
    normalized, error = _normalize_entries(entries)
    if error is not None:
        return error
    assert normalized is not None

    parsed_rules, rules_error = _normalize_rules(rules)
    if rules_error is not None:
        return rules_error
    assert parsed_rules is not None

    source_manifest_digest = _digest(
        {"entries": [_manifest_entry(entry) for entry in normalized]}
    )
    rules_digest = _digest(
        {
            "field_renames": parsed_rules.field_renames,
            "path_redirects": parsed_rules.path_redirects,
            "anchor_redirects": parsed_rules.anchor_redirects,
            "supported_asset_extensions": sorted(parsed_rules.supported_asset_extensions),
            "execution_grants": sorted(parsed_rules.execution_grants),
        }
    )

    path_set = {entry["path"] for entry in normalized}
    anchors_by_path = {
        entry["path"]: _collect_anchors(entry["content"]) for entry in normalized
    }

    findings: list[RawFinding] = []
    report_links: list[dict[str, object]] = []
    report_frontmatter: list[dict[str, object]] = []
    targets: list[dict[str, str]] = []
    file_entries: list[dict[str, object]] = []
    patch_files: list[dict[str, object]] = []
    patch_bytes = 0
    patch_truncated = False

    for entry in normalized:
        path = entry["path"]
        source = entry["content"]
        rewritten, fm_rows, fm_findings = _rewrite_frontmatter(
            path, source, parsed_rules.field_renames
        )
        report_frontmatter.extend(fm_rows)
        findings.extend(fm_findings)

        rewritten, link_rows, link_findings = _rewrite_links_and_assets(
            path=path,
            content=rewritten,
            rules=parsed_rules,
            path_set=path_set,
            anchors_by_path=anchors_by_path,
        )
        report_links.extend(link_rows)
        findings.extend(link_findings)

        source_digest = hashlib.sha256(
            unicodedata.normalize("NFC", source).encode("utf-8")
        ).hexdigest()
        target_digest = hashlib.sha256(
            unicodedata.normalize("NFC", rewritten).encode("utf-8")
        ).hexdigest()
        changed = source_digest != target_digest
        file_entries.append(
            {
                "path": path,
                "source_digest": source_digest,
                "target_digest": target_digest,
                "changed": changed,
            }
        )
        if changed:
            targets.append({"path": path, "content": rewritten})
            unified = _unified_diff(path, source, rewritten)
            encoded = unified.encode("utf-8")
            if not patch_truncated and patch_bytes + len(encoded) <= MAX_PATCH_BYTES:
                patch_files.append({"path": path, "unified_diff": unified})
                patch_bytes += len(encoded)
            else:
                patch_truncated = True

    findings_payload = [_serialize_finding(raw) for raw in findings]
    findings_payload.sort(key=_finding_sort_key)
    findings_truncated = len(findings_payload) > MAX_FINDINGS
    if findings_truncated:
        findings_payload = findings_payload[:MAX_FINDINGS]

    report_links.sort(
        key=lambda row: (
            str(row.get("path", "")),
            str(row.get("kind", "")),
            str(row.get("before", "")),
            str(row.get("after", "")),
        )
    )
    report_frontmatter.sort(
        key=lambda row: (
            str(row.get("path", "")),
            str(row.get("before_key", "")),
            str(row.get("after_key", "")),
        )
    )
    patch_files.sort(key=lambda row: str(row["path"]))
    file_entries.sort(key=lambda row: str(row["path"]))
    targets.sort(key=lambda row: row["path"])

    report = {
        "links": report_links,
        "frontmatter": report_frontmatter,
    }
    patch_body = {
        "files": patch_files,
        "truncated": patch_truncated,
    }
    patch_digest = _digest(patch_body)
    mapping_digest = _digest(
        {
            "links": report_links,
            "frontmatter": report_frontmatter,
        }
    )
    migrate_body = {
        "source_manifest_digest": source_manifest_digest,
        "rules_digest": rules_digest,
        "file_entries": file_entries,
        "patch_digest": patch_digest,
        "mapping_digest": mapping_digest,
        "findings": findings_payload,
        "findings_truncated": findings_truncated,
    }
    migrate_digest = _digest(migrate_body)
    return {
        **migrate_body,
        "migrate_digest": migrate_digest,
        "patch": patch_body,
        "report": report,
        "targets": targets,
        "entry_count": len(normalized),
        "changed_count": sum(1 for item in file_entries if item["changed"]),
        "finding_count": len(findings_payload),
    }


def verify_migrate(payload: Mapping[str, Any]) -> dict[str, object]:
    """Recompute digests for a migrate payload (excluding ephemeral patch text)."""
    required = (
        "source_manifest_digest",
        "rules_digest",
        "file_entries",
        "patch_digest",
        "mapping_digest",
        "findings",
        "migrate_digest",
    )
    missing = [key for key in required if key not in payload]
    if missing:
        return {"verified": False, "error": "missing_fields", "missing": missing}

    findings = payload["findings"]
    if not isinstance(findings, list):
        return {"verified": False, "error": "findings_invalid"}
    for item in findings:
        if not isinstance(item, Mapping):
            return {"verified": False, "error": "finding_invalid"}
        if item.get("class") not in {
            "safe",
            "transformable",
            "decision_required",
            "unsupported",
            "malformed",
        }:
            return {"verified": False, "error": "class_invalid", "class": item.get("class")}
        expected = item.get("finding_digest")
        if not isinstance(expected, str):
            return {"verified": False, "error": "finding_digest_invalid"}
        if _finding_digest(item) != expected:
            return {
                "verified": False,
                "error": "finding_digest_mismatch",
                "expected": _finding_digest(item),
                "received": expected,
            }

    file_entries = payload["file_entries"]
    if not isinstance(file_entries, list):
        return {"verified": False, "error": "file_entries_invalid"}

    body = {
        "source_manifest_digest": payload["source_manifest_digest"],
        "rules_digest": payload["rules_digest"],
        "file_entries": sorted(file_entries, key=lambda row: str(row["path"])),
        "patch_digest": payload["patch_digest"],
        "mapping_digest": payload["mapping_digest"],
        "findings": sorted(findings, key=_finding_sort_key),
        "findings_truncated": bool(payload.get("findings_truncated", False)),
    }
    expected = _digest(body)
    if payload["migrate_digest"] != expected:
        return {
            "verified": False,
            "error": "migrate_digest_mismatch",
            "expected": expected,
            "received": payload["migrate_digest"],
        }
    return {"verified": True}


def canonical_json_bytes(value: Any) -> bytes:
    """ADR 0008 canonical JSON: sorted keys, compact separators, NFC strings."""
    import json

    return json.dumps(
        _nfc_normalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _normalize_entries(
    entries: Sequence[Mapping[str, Any]] | None,
) -> tuple[list[dict[str, str]] | None, dict[str, object] | None]:
    if entries is None:
        return None, {"error": "entries_required"}
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        return None, {"error": "entries_invalid"}

    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in entries:
        if not isinstance(item, Mapping):
            return None, {"error": "entry_invalid"}
        path = item.get("path")
        content = item.get("content")
        if not isinstance(path, str) or not path.strip():
            return None, {"error": "path_invalid", "path": path}
        if len(path) > MAX_PATH_LEN or not _PATH_RE.fullmatch(path):
            return None, {"error": "path_invalid", "path": path}
        if path.startswith("/") or path.startswith("../") or "/../" in f"/{path}/":
            return None, {"error": "path_traversal", "path": path}
        if not isinstance(content, str):
            return None, {"error": "content_invalid", "path": path}
        if path in seen:
            return None, {"error": "path_duplicate", "path": path}
        content_bytes = unicodedata.normalize("NFC", content).encode("utf-8")
        if len(content_bytes) > MAX_ENTRY_BYTES:
            return None, {"error": "content_too_large", "path": path}
        seen.add(path)
        normalized.append({"path": path, "content": content})

    if not normalized:
        return None, {"error": "entries_empty"}
    if len(normalized) > MAX_ENTRIES:
        return None, {"error": "entries_too_many", "count": len(normalized)}
    normalized.sort(key=lambda entry: entry["path"])
    return normalized, None


def _normalize_rules(
    rules: Mapping[str, Any] | None,
) -> tuple[ParsedRules | None, dict[str, object] | None]:
    if rules is None:
        rules = {}
    if not isinstance(rules, Mapping):
        return None, {"error": "rules_invalid"}
    allowed = {
        "field_renames",
        "path_redirects",
        "anchor_redirects",
        "supported_asset_extensions",
        "execution_grants",
    }
    unknown = set(rules) - allowed
    if unknown:
        return None, {"error": "rules_unknown_fields", "fields": sorted(unknown)}

    field_renames, err = _string_map(rules.get("field_renames", {}), "field_renames")
    if err is not None:
        return None, err
    path_redirects, err = _string_map(rules.get("path_redirects", {}), "path_redirects")
    if err is not None:
        return None, err
    for key, value in path_redirects.items():
        if _is_unsafe_path(key) or _is_unsafe_path(value):
            return None, {
                "error": "rules_path_unsafe",
                "field": "path_redirects",
                "path": key if _is_unsafe_path(key) else value,
            }
    anchor_redirects, err = _string_map(
        rules.get("anchor_redirects", {}), "anchor_redirects"
    )
    if err is not None:
        return None, err

    extensions_raw = rules.get(
        "supported_asset_extensions", list(DEFAULT_SUPPORTED_ASSET_EXTENSIONS)
    )
    if not isinstance(extensions_raw, list) or not extensions_raw:
        return None, {"error": "supported_asset_extensions_invalid"}
    extensions: set[str] = set()
    for item in extensions_raw:
        if not isinstance(item, str) or not item:
            return None, {"error": "supported_asset_extensions_invalid"}
        ext = item if item.startswith(".") else f".{item}"
        extensions.add(ext.lower())

    grants_raw = rules.get("execution_grants", [])
    if not isinstance(grants_raw, list):
        return None, {"error": "execution_grants_invalid"}
    grants: set[str] = set()
    for item in grants_raw:
        if not isinstance(item, str) or item not in EXECUTION_GRANTS:
            return None, {"error": "execution_grants_invalid", "grant": item}
        grants.add(item)

    assert field_renames is not None
    assert path_redirects is not None
    assert anchor_redirects is not None
    return (
        ParsedRules(
            field_renames=field_renames,
            path_redirects=path_redirects,
            anchor_redirects=anchor_redirects,
            supported_asset_extensions=frozenset(extensions),
            execution_grants=frozenset(grants),
        ),
        None,
    )


def _string_map(
    value: object, field: str
) -> tuple[dict[str, str] | None, dict[str, object] | None]:
    if not isinstance(value, Mapping):
        return None, {"error": f"{field}_invalid"}
    if len(value) > MAX_RULE_MAP_ENTRIES:
        return None, {"error": f"{field}_too_many", "count": len(value)}
    result: dict[str, str] = {}
    for key, mapped in value.items():
        if not isinstance(key, str) or not key or not isinstance(mapped, str) or not mapped:
            return None, {"error": f"{field}_invalid"}
        result[key] = mapped
    return dict(sorted(result.items())), None


def _rewrite_frontmatter(
    path: str, content: str, field_renames: Mapping[str, str]
) -> tuple[str, list[dict[str, object]], list[RawFinding]]:
    rows: list[dict[str, object]] = []
    findings: list[RawFinding] = []
    match = _FRONTMATTER_RE.match(content)
    if match is None:
        if content.lstrip().startswith("---"):
            findings.append(
                RawFinding(
                    feature_id="md.frontmatter.malformed",
                    class_="malformed",
                    path=path,
                    line=1,
                    column=1,
                    message="frontmatter fence is malformed",
                )
            )
        return content, rows, findings

    body = match.group(1)
    lines = body.split("\n")
    rewritten_lines: list[str] = []
    for offset, line in enumerate(lines, start=2):
        fm_match = _FM_LINE_RE.match(line)
        if not fm_match:
            rewritten_lines.append(line)
            continue
        indent, key, sep, rest = fm_match.groups()
        if key in field_renames:
            new_key = field_renames[key]
            rewritten_lines.append(f"{indent}{new_key}{sep}{rest}")
            rows.append(
                {
                    "path": path,
                    "before_key": key,
                    "after_key": new_key,
                    "status": "renamed",
                }
            )
            findings.append(
                RawFinding(
                    feature_id="md.frontmatter.field_rename",
                    class_="transformable",
                    path=path,
                    line=offset,
                    column=fm_match.start(2) + 1,
                    message=f"{key}->{new_key}",
                )
            )
        else:
            rewritten_lines.append(line)
            rows.append(
                {
                    "path": path,
                    "before_key": key,
                    "after_key": key,
                    "status": "preserved",
                }
            )

    new_fm = "---\n" + "\n".join(rewritten_lines) + "\n---\n"
    remainder = content[match.end() :]
    if content[match.end() - 1 :][:1] == "\n" and not remainder.startswith("\n"):
        # keep body separation stable when original had trailing newline after fence
        pass
    return new_fm + remainder, rows, findings


def _rewrite_links_and_assets(
    *,
    path: str,
    content: str,
    rules: ParsedRules,
    path_set: set[str],
    anchors_by_path: Mapping[str, set[str]],
) -> tuple[str, list[dict[str, object]], list[RawFinding]]:
    rows: list[dict[str, object]] = []
    findings: list[RawFinding] = []
    parts: list[str] = []
    cursor = 0
    for match in _LINK_RE.finditer(content):
        parts.append(content[cursor : match.start()])
        prefix = match.group(1)
        target = match.group(2).strip()
        is_asset = prefix.startswith("!")
        kind = "asset" if is_asset else "link"
        line = content.count("\n", 0, match.start()) + 1
        column = match.start() - content.rfind("\n", 0, match.start())
        after, status, finding = _resolve_target(
            path=path,
            target=target,
            is_asset=is_asset,
            rules=rules,
            path_set=path_set,
            anchors_by_path=anchors_by_path,
            line=line,
            column=column,
        )
        rows.append(
            {
                "path": path,
                "kind": kind,
                "before": target,
                "after": after,
                "status": status,
            }
        )
        if finding is not None:
            findings.append(finding)
        parts.append(f"{prefix}({after})")
        cursor = match.end()
    parts.append(content[cursor:])
    return "".join(parts), rows, findings


def _resolve_target(
    *,
    path: str,
    target: str,
    is_asset: bool,
    rules: ParsedRules,
    path_set: set[str],
    anchors_by_path: Mapping[str, set[str]],
    line: int,
    column: int,
) -> tuple[str, str, RawFinding | None]:
    if not target:
        return (
            target,
            "unresolved",
            RawFinding(
                feature_id="md.link.empty",
                class_="malformed",
                path=path,
                line=line,
                column=column,
                message="empty link target",
            ),
        )

    if _is_external(target):
        if "fetch_remote_urls" in rules.execution_grants or (
            is_asset and "copy_external_assets" in rules.execution_grants
        ):
            # Grant acknowledges external targets but this star still does not fetch.
            return (
                target,
                "external_granted",
                RawFinding(
                    feature_id="md.link.external_granted",
                    class_="decision_required",
                    path=path,
                    line=line,
                    column=column,
                    message=target,
                ),
            )
        return (
            target,
            "external",
            RawFinding(
                feature_id="md.link.external",
                class_="decision_required",
                path=path,
                line=line,
                column=column,
                message=target,
            ),
        )

    if target.startswith(("mailto:", "tel:")):
        return target, "preserved", None

    path_part, anchor = _split_anchor(target)
    if path_part == "" and anchor:
        # Same-document anchor.
        redirected = rules.anchor_redirects.get(anchor, anchor)
        after = f"#{redirected}"
        status = "rewritten" if redirected != anchor else "preserved"
        if redirected not in anchors_by_path.get(path, set()):
            return (
                after,
                "unresolved",
                RawFinding(
                    feature_id="md.anchor.unresolved",
                    class_="decision_required",
                    path=path,
                    line=line,
                    column=column,
                    message=after,
                ),
            )
        finding = None
        if status == "rewritten":
            finding = RawFinding(
                feature_id="md.anchor.redirect",
                class_="transformable",
                path=path,
                line=line,
                column=column,
                message=f"#{anchor}->#{redirected}",
            )
        return after, status, finding

    resolved = _resolve_relative(path, path_part)
    if resolved is None:
        return (
            target,
            "unsafe",
            RawFinding(
                feature_id="md.link.path_traversal",
                class_="unsupported",
                path=path,
                line=line,
                column=column,
                message=target,
            ),
        )

    redirected_path = rules.path_redirects.get(resolved, resolved)
    if redirected_path != resolved:
        status_base = "redirect"
        finding_id = "md.link.redirect"
        class_: FeatureClass = "transformable"
    else:
        status_base = "preserved"
        finding_id = ""
        class_ = "safe"

    if _is_unsafe_path(redirected_path):
        return (
            target,
            "unsafe",
            RawFinding(
                feature_id="md.link.path_traversal",
                class_="unsupported",
                path=path,
                line=line,
                column=column,
                message=target,
            ),
        )

    after_path = _relativize(path, redirected_path)
    after_anchor = rules.anchor_redirects.get(anchor, anchor) if anchor else ""
    after = after_path if not after_anchor else f"{after_path}#{after_anchor}"

    if is_asset:
        ext = posixpath.splitext(redirected_path)[1].lower()
        if ext and ext not in rules.supported_asset_extensions:
            return (
                after,
                "unsupported",
                RawFinding(
                    feature_id="md.asset.unsupported",
                    class_="unsupported",
                    path=path,
                    line=line,
                    column=column,
                    message=after,
                ),
            )

    if (
        redirected_path not in path_set
        and not is_asset
        and (
            redirected_path.endswith((".md", ".mdx", ".rst"))
            or "." not in posixpath.basename(redirected_path)
        )
    ):
        # Relative doc links must resolve inside the supplied tree.
        return (
            after,
            "unresolved",
            RawFinding(
                feature_id="md.link.unresolved",
                class_="decision_required",
                path=path,
                line=line,
                column=column,
                message=after,
            ),
        )

    if after_anchor:
        known = anchors_by_path.get(redirected_path, set())
        # If target doc is outside the tree (asset-like), skip anchor check.
        if redirected_path in anchors_by_path and after_anchor not in known:
            return (
                after,
                "unresolved",
                RawFinding(
                    feature_id="md.anchor.unresolved",
                    class_="decision_required",
                    path=path,
                    line=line,
                    column=column,
                    message=after,
                ),
            )

    finding = None
    status = status_base
    if after_anchor and rules.anchor_redirects.get(anchor, anchor) != anchor:
        status = "rewritten"
        finding = RawFinding(
            feature_id="md.anchor.redirect",
            class_="transformable",
            path=path,
            line=line,
            column=column,
            message=f"{target}->{after}",
        )
    elif status_base == "redirect":
        finding = RawFinding(
            feature_id=finding_id,
            class_=class_,
            path=path,
            line=line,
            column=column,
            message=f"{target}->{after}",
        )
    elif after != target:
        status = "rewritten"
    return after, status, finding


def _split_anchor(target: str) -> tuple[str, str]:
    if "#" not in target:
        return target, ""
    path_part, anchor = target.split("#", 1)
    return path_part, anchor


def _is_external(target: str) -> bool:
    lowered = target.lower()
    if lowered.startswith(("http://", "https://", "//")):
        return True
    parts = urlsplit(target)
    return bool(parts.scheme and parts.netloc)


def _is_unsafe_path(path: str) -> bool:
    if not path or path.startswith("/") or path.startswith("../"):
        return True
    if "/../" in f"/{path}/" or path.endswith("/..") or "\\" in path:
        return True
    return bool(not _PATH_RE.fullmatch(path))


def _resolve_relative(from_path: str, target: str) -> str | None:
    if target.startswith("/"):
        return None
    base_dir = posixpath.dirname(from_path)
    joined = posixpath.normpath(posixpath.join(base_dir, target) if base_dir else target)
    if joined.startswith("../") or joined == "..":
        return None
    if joined.startswith("/"):
        joined = joined.lstrip("/")
    if _is_unsafe_path(joined):
        return None
    return joined


def _relativize(from_path: str, target_path: str) -> str:
    base_dir = posixpath.dirname(from_path)
    if not base_dir:
        return target_path if target_path.startswith(".") else f"./{target_path}"
    rel = posixpath.relpath(target_path, base_dir)
    if not rel.startswith("."):
        return f"./{rel}"
    return rel


def _collect_anchors(content: str) -> set[str]:
    body = content
    fm = _FRONTMATTER_RE.match(content)
    if fm is not None:
        body = content[fm.end() :]
    anchors: set[str] = set()
    for _hashes, title in _HEADING_RE.findall(body):
        anchors.add(_slugify(title))
    return anchors


def _slugify(title: str) -> str:
    text = unicodedata.normalize("NFKD", title.strip().lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "-", text).strip("-")
    return text


def _unified_diff(path: str, before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )


def _manifest_entry(entry: Mapping[str, str]) -> dict[str, str]:
    content = unicodedata.normalize("NFC", entry["content"])
    return {
        "path": entry["path"],
        "content_digest": hashlib.sha256(content.encode("utf-8")).hexdigest(),
    }


def _nfc_normalize(value: Any) -> Any:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, Mapping):
        return {key: _nfc_normalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_nfc_normalize(item) for item in value]
    return value


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _serialize_finding(raw: RawFinding) -> dict[str, object]:
    payload: dict[str, object] = {
        "feature_id": raw.feature_id,
        "class": raw.class_,
        "path": raw.path,
        "span": {"line": raw.line, "column": raw.column},
    }
    if raw.message:
        message = unicodedata.normalize("NFC", raw.message)
        if len(message.encode("utf-8")) > MAX_MESSAGE_BYTES:
            message = message.encode("utf-8")[:MAX_MESSAGE_BYTES].decode("utf-8", "ignore")
        payload["message"] = message
    payload["finding_digest"] = _finding_digest(payload)
    return payload


def _finding_digest(finding: Mapping[str, Any]) -> str:
    body: dict[str, Any] = {
        "feature_id": finding["feature_id"],
        "class": finding["class"],
        "path": finding["path"],
    }
    span = finding.get("span")
    if isinstance(span, Mapping):
        body["span"] = {"column": span["column"], "line": span["line"]}
    message = finding.get("message")
    if isinstance(message, str) and message:
        body["message"] = message
    return _digest(body)


def _finding_sort_key(finding: Mapping[str, Any]) -> tuple[Any, ...]:
    span = finding.get("span") if isinstance(finding.get("span"), Mapping) else {}
    return (
        finding.get("path", ""),
        span.get("line", 0),
        span.get("column", 0),
        finding.get("feature_id", ""),
        finding.get("class", ""),
    )
