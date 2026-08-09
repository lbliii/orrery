"""Regression checks for the production image's source and dependency contract."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dockerfile_tracks_chirp_main_and_copies_full_source() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text()

    assert (
        "FROM python:3.14-slim@sha256:"
        "a7fb1e634c4a578f9e0bd6327f11a3cde11b7a9395f48e24360c0988bcc5c2bc" in dockerfile
    )
    assert (
        "ghcr.io/astral-sh/uv@sha256:"
        "2d890623d310b57771ce840f0da5eed5fc6d657da05ffaa45d82797b53fa3abc" in dockerfile
    )
    assert "RUN uv venv --python 3.14 /opt/venv" in dockerfile
    assert "ARG GIT_REF=main" in dockerfile
    assert (
        'ADD "https://api.github.com/repos/lbliii/chirp/commits/${GIT_REF}" '
        "/tmp/chirp-commit.json" in dockerfile
    )
    assert (
        '"bengal-chirp[skill,sessions] @ '
        'git+https://github.com/lbliii/chirp.git@${GIT_REF}"' in dockerfile
    )
    assert '"itsdangerous>=2.2.0"' in dockerfile
    assert "uv sync --frozen" not in dockerfile
    assert "uv.lock" not in dockerfile
    assert "COPY . /app/" in dockerfile

    # A hand-maintained package allowlist caused prior Railway start-up failures.
    assert "COPY catalog /app/catalog/" not in dockerfile
    assert "COPY commerce /app/commerce/" not in dockerfile


def test_dockerignore_keeps_runtime_roots_in_the_build_context() -> None:
    ignored = (ROOT / ".dockerignore").read_text().splitlines()
    ignored_patterns = {
        line.strip() for line in ignored if line.strip() and not line.startswith("#")
    }

    required_roots = {
        "app.py",
        "catalog",
        "commerce",
        "trust",
        "stars",
        "pages",
        "static",
    }
    assert not required_roots & ignored_patterns
    assert "*" not in ignored_patterns
    assert {
        ".git",
        ".env",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        ".idea",
        ".vscode",
    } <= ignored_patterns
