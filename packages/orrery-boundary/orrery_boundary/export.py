"""``local/export-at-ref`` — inventory tracked files at a git SHA."""

from __future__ import annotations

import hashlib
import re
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Final

# Mirror stars/manifest_bind/contract.py FILE_ENTRY_SCHEMA constraints.
MAX_FILES: Final = 10_000
MAX_PATH_LEN: Final = 512
_SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
_PATH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")


def export_at_ref(
    ref: str,
    *,
    repo_root: str | Path | None = None,
    paths: Sequence[str] | None = None,
) -> dict[str, object]:
    """Export tracked files at ``ref`` as ``{files: [{path, sha256, size}]}``.

    Output is shaped for hosted ``orrery/manifest-bind``. Orrery never opens
    the caller's repo — this local adapter does.
    """
    if not isinstance(ref, str) or not _SHA_RE.fullmatch(ref):
        return {"error": "ref_invalid", "ref": ref}

    root = Path(repo_root).resolve() if repo_root is not None else Path.cwd().resolve()
    if not _git_ok(root):
        return {"error": "repo_invalid", "repo_root": str(root)}

    resolved = _resolve_ref(root, ref)
    if resolved is None:
        return {"error": "ref_not_found", "ref": ref, "repo_root": str(root)}

    listed = _list_paths(root, resolved)
    if listed is None:
        return {"error": "list_failed", "ref": resolved, "repo_root": str(root)}

    wanted: set[str] | None = None
    if paths is not None:
        if not isinstance(paths, list | tuple):
            return {"error": "paths_invalid"}
        wanted = set()
        for index, path in enumerate(paths):
            if not isinstance(path, str) or not path:
                return {"error": "path_invalid", "index": index}
            if path.startswith("/") or path.startswith("../") or "/../" in f"/{path}/":
                return {"error": "path_traversal", "path": path, "index": index}
            wanted.add(path)

    files: list[dict[str, object]] = []
    for path in listed:
        if wanted is not None and path not in wanted:
            continue
        if not _admit_path(path):
            continue
        blob = _show_blob(root, resolved, path)
        if blob is None:
            continue
        files.append(
            {
                "path": path,
                "sha256": hashlib.sha256(blob).hexdigest(),
                "size": len(blob),
            }
        )
        if len(files) > MAX_FILES:
            return {"error": "files_too_many", "max_files": MAX_FILES}

    files.sort(key=lambda item: str(item["path"]))
    return {
        "files": files,
        "ref": resolved,
        "repo_root": str(root),
        "file_count": len(files),
    }


def _admit_path(path: str) -> bool:
    if not path or len(path) > MAX_PATH_LEN:
        return False
    if path.startswith("/") or path.startswith("../") or "/../" in f"/{path}/":
        return False
    return bool(_PATH_RE.fullmatch(path))


def _git_ok(root: Path) -> bool:
    stdout = _run_text(root, ["rev-parse", "--is-inside-work-tree"])
    return stdout is not None and stdout.strip() == "true"


def _resolve_ref(root: Path, ref: str) -> str | None:
    stdout = _run_text(root, ["rev-parse", "--verify", f"{ref}^{{commit}}"])
    if stdout is None:
        return None
    return stdout.strip()


def _list_paths(root: Path, ref: str) -> list[str] | None:
    stdout = _run_text(root, ["ls-tree", "-r", "--name-only", "-z", ref])
    if stdout is None:
        return None
    if not stdout:
        return []
    return [part for part in stdout.split("\0") if part]


def _show_blob(root: Path, ref: str, path: str) -> bytes | None:
    return _run_bytes(root, ["show", f"{ref}:{path}"])


def _run_text(root: Path, args: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout


def _run_bytes(root: Path, args: list[str]) -> bytes | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=root,
            check=False,
            capture_output=True,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout
