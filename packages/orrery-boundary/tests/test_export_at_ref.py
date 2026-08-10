"""Acceptance tests for local/export-at-ref (#224)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from orrery_boundary.export import export_at_ref
from orrery_boundary.server import TOOL_NAMES

from stars.manifest_bind.service import bind


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


@pytest.fixture
def sample_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "boundary@example.com")
    _git(repo, "config", "user.name", "Boundary")
    (repo / "docs").mkdir()
    (repo / "docs" / "plan.md").write_text("# plan\n", encoding="utf-8")
    (repo / "docs" / "readme.md").write_text("hello\n", encoding="utf-8")
    (repo / "skip space.txt").write_text("ignored charset\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "seed")
    sha = _git(repo, "rev-parse", "HEAD")
    return repo, sha


@pytest.mark.issue(224)
def test_export_at_ref_validates_via_manifest_bind(
    sample_repo: tuple[Path, str],
) -> None:
    repo, sha = sample_repo
    exported = export_at_ref(sha, repo_root=repo, paths=["docs/plan.md", "docs/readme.md"])
    assert "error" not in exported
    files = exported["files"]
    assert isinstance(files, list)
    assert {row["path"] for row in files} == {"docs/plan.md", "docs/readme.md"}

    bound = bind(files)
    assert "error" not in bound
    assert bound["admitted_count"] == 2
    assert bound["excluded_count"] == 0
    assert isinstance(bound["manifest_digest"], str)
    assert len(bound["manifest_digest"]) == 64


@pytest.mark.issue(224)
def test_export_skips_paths_outside_manifest_charset(
    sample_repo: tuple[Path, str],
) -> None:
    repo, sha = sample_repo
    exported = export_at_ref(sha, repo_root=repo)
    assert "error" not in exported
    paths = {row["path"] for row in exported["files"]}  # type: ignore[union-attr]
    assert "docs/plan.md" in paths
    assert "skip space.txt" not in paths


@pytest.mark.issue(224)
def test_mcp_registers_locality_tools() -> None:
    assert TOOL_NAMES == ("local/export-at-ref", "local/witness-approve")
