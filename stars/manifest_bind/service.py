"""Pure bind of caller-supplied file inventories into a stable manifest digest."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from .contract import MAX_FILES, MAX_PATH_LEN, SHA256_HEX_LEN

_SHA256_RE = re.compile(rf"^[0-9a-f]{{{SHA256_HEX_LEN}}}$")
_PATH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")


def bind(files: object) -> dict[str, object]:
    """Admit well-formed file entries and seal a deterministic ``manifest_digest``."""
    if not isinstance(files, list):
        return {"error": "files_invalid"}
    if len(files) > MAX_FILES:
        return {"error": "files_too_many", "max_files": MAX_FILES}

    admitted: list[dict[str, object]] = []
    excluded: list[dict[str, object]] = []
    seen_paths: dict[str, int] = {}

    for index, raw in enumerate(files):
        parsed = _parse_entry(raw, index)
        if "error" in parsed:
            excluded.append(parsed)
            continue
        path = str(parsed["path"])
        if path in seen_paths:
            excluded.append(
                {
                    "error": "duplicate_path",
                    "path": path,
                    "index": index,
                    "first_index": seen_paths[path],
                }
            )
            continue
        seen_paths[path] = index
        admitted.append({"path": path, "sha256": parsed["sha256"], "size": parsed["size"]})

    admitted.sort(key=lambda item: str(item["path"]))
    digest = manifest_digest(admitted)
    return {
        "manifest_digest": digest,
        "admitted_count": len(admitted),
        "excluded_count": len(excluded),
        "admitted": admitted,
        "excluded": excluded,
    }


def manifest_digest(admitted: Sequence[Mapping[str, Any]]) -> str:
    """Lowercase hex sha256 over canonical admitted ``{path, sha256, size}`` rows."""
    rows = [
        {"path": str(item["path"]), "sha256": str(item["sha256"]), "size": int(item["size"])}
        for item in admitted
    ]
    rows.sort(key=lambda item: item["path"])
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def _parse_entry(raw: object, index: int) -> dict[str, object]:
    if not isinstance(raw, Mapping):
        return {"error": "entry_not_object", "index": index}
    if set(raw) - {"path", "sha256", "size"}:
        return {"error": "entry_unknown_fields", "index": index}

    path = raw.get("path")
    sha256 = raw.get("sha256")
    size = raw.get("size")

    if not isinstance(path, str) or not path or len(path) > MAX_PATH_LEN:
        return {"error": "path_invalid", "index": index}
    if path.startswith("/") or path.startswith("../") or "/../" in f"/{path}/":
        return {"error": "path_traversal", "path": path, "index": index}
    if not _PATH_RE.fullmatch(path):
        return {"error": "path_invalid", "path": path, "index": index}

    if not isinstance(sha256, str) or not _SHA256_RE.fullmatch(sha256):
        return {"error": "sha256_invalid", "path": path, "index": index}

    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        return {"error": "size_invalid", "path": path, "index": index}

    return {"path": path, "sha256": sha256, "size": size}
