"""Pure patch capture over caller-supplied before/after file snapshots."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from stars.manifest_bind.service import bind as bind_manifest

from .contract import MAX_CONTENT_BYTES, MAX_FILES


def capture(before: object, after: object) -> dict[str, object]:
    """Diff two caller snapshots into a sealed patch digest without retaining bytes."""
    before_map, before_err = _snapshot_map(before, "before")
    if before_err is not None:
        return before_err
    after_map, after_err = _snapshot_map(after, "after")
    if after_err is not None:
        return after_err

    assert before_map is not None and after_map is not None
    before_paths = set(before_map)
    after_paths = set(after_map)

    added = sorted(after_paths - before_paths)
    removed = sorted(before_paths - after_paths)
    shared = sorted(before_paths & after_paths)
    modified = [
        path
        for path in shared
        if before_map[path]["sha256"] != after_map[path]["sha256"]
        or before_map[path]["size"] != after_map[path]["size"]
    ]

    lines_added = 0
    lines_removed = 0
    for path in added:
        lines_added += _line_count(after_map[path].get("content"))
    for path in removed:
        lines_removed += _line_count(before_map[path].get("content"))
    for path in modified:
        add, remove = _line_delta(before_map[path].get("content"), after_map[path].get("content"))
        lines_added += add
        lines_removed += remove

    changed_paths = sorted({*added, *removed, *modified})
    change_rows = [
        {
            "path": path,
            "before_sha256": None if path in added else before_map[path]["sha256"],
            "after_sha256": None if path in removed else after_map[path]["sha256"],
            "before_size": None if path in added else before_map[path]["size"],
            "after_size": None if path in removed else after_map[path]["size"],
        }
        for path in changed_paths
    ]
    digest = patch_digest(change_rows)
    return {
        "patch_digest": digest,
        "changed_paths": changed_paths,
        "added_paths": added,
        "removed_paths": removed,
        "modified_paths": modified,
        "line_stats": {"added": lines_added, "removed": lines_removed},
        "before_manifest_digest": _manifest_only(before_map),
        "after_manifest_digest": _manifest_only(after_map),
    }


def patch_digest(change_rows: list[dict[str, object]]) -> str:
    """Lowercase hex sha256 over canonical changed-path rows (no content bytes)."""
    rows = sorted(change_rows, key=lambda item: str(item["path"]))
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def _snapshot_map(
    snapshot: object, side: str
) -> tuple[dict[str, dict[str, Any]] | None, dict[str, object] | None]:
    if not isinstance(snapshot, Mapping) or set(snapshot) - {"files"} or "files" not in snapshot:
        return None, {"error": "snapshot_invalid", "side": side}
    files = snapshot["files"]
    if not isinstance(files, list) or len(files) > MAX_FILES:
        return None, {"error": "files_invalid", "side": side}

    # Bind ignores unknown fields; strip content first for digest admission.
    stripped: list[dict[str, object]] = []
    contents: dict[str, str] = {}
    for index, raw in enumerate(files):
        if not isinstance(raw, Mapping):
            return None, {"error": "entry_not_object", "side": side, "index": index}
        content = raw.get("content")
        entry = {key: value for key, value in raw.items() if key != "content"}
        if content is not None:
            if not isinstance(content, str):
                return None, {"error": "content_invalid", "side": side, "index": index}
            if len(content.encode()) > MAX_CONTENT_BYTES:
                return None, {"error": "content_too_large", "side": side, "index": index}
            path = entry.get("path")
            if isinstance(path, str):
                contents[path] = content
        stripped.append(dict(entry))

    bound = bind_manifest(stripped)
    if "error" in bound:
        err = dict(bound)
        err["side"] = side
        return None, err
    if bound["excluded_count"]:
        return None, {
            "error": "manifest_incomplete",
            "side": side,
            "excluded_count": bound["excluded_count"],
            "excluded": bound["excluded"],
        }

    admitted = bound["admitted"]
    assert isinstance(admitted, list)
    result: dict[str, dict[str, Any]] = {}
    for item in admitted:
        assert isinstance(item, Mapping)
        path = str(item["path"])
        row: dict[str, Any] = {
            "path": path,
            "sha256": str(item["sha256"]),
            "size": int(item["size"]),
        }
        if path in contents:
            row["content"] = contents[path]
        result[path] = row
    return result, None


def _manifest_only(file_map: Mapping[str, Mapping[str, Any]]) -> str:
    files = [
        {"path": path, "sha256": row["sha256"], "size": row["size"]}
        for path, row in sorted(file_map.items())
    ]
    return str(bind_manifest(files)["manifest_digest"])


def _line_count(content: object) -> int:
    if not isinstance(content, str):
        return 0
    if content == "":
        return 0
    return len(content.splitlines())


def _line_delta(before: object, after: object) -> tuple[int, int]:
    if not isinstance(before, str) or not isinstance(after, str):
        return 0, 0
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    # Multiset-style line accounting keeps the receipt deterministic without
    # embedding a full unified diff (raw bytes stay private / optional).
    before_counts: dict[str, int] = {}
    after_counts: dict[str, int] = {}
    for line in before_lines:
        before_counts[line] = before_counts.get(line, 0) + 1
    for line in after_lines:
        after_counts[line] = after_counts.get(line, 0) + 1
    removed = 0
    added = 0
    for line, count in before_counts.items():
        delta = count - after_counts.get(line, 0)
        if delta > 0:
            removed += delta
    for line, count in after_counts.items():
        delta = count - before_counts.get(line, 0)
        if delta > 0:
            added += delta
    return added, removed
