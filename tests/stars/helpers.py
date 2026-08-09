"""Shared L0 star-eval helpers — allowlist negatives + contract holds (#116)."""

from __future__ import annotations

import tomllib
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
STARS_ROOT = ROOT / "stars"


def load_star_manifest(package: str) -> dict[str, Any]:
    """Load ``stars/<package>/star.toml`` as a decoded mapping."""
    path = STARS_ROOT / package / "star.toml"
    return tomllib.loads(path.read_text(encoding="utf-8"))


def assert_tool_schema_keys(schemas: Mapping[str, Any], expected: set[str]) -> None:
    """Assert contract ``tool_schemas()`` exposes exactly ``expected`` tools."""
    assert set(schemas) == expected, f"tool schemas {set(schemas)!r} != {expected!r}"


def assert_payload_keys(payload: Mapping[str, Any], required: Sequence[str]) -> None:
    """Assert a service payload contains every required key."""
    missing = [key for key in required if key not in payload]
    assert not missing, f"payload missing keys {missing}: {sorted(payload)}"


def assert_allowlist_rejects(
    call: Callable[..., Mapping[str, Any]],
    *args: Any,
    error: str = "source_not_allowed",
    **kwargs: Any,
) -> Mapping[str, Any]:
    """Call an allowlisted service with a bad SKU/URL and assert a loud fail.

    Source-watch-style services return an error payload rather than raising.
    """
    result = call(*args, **kwargs)
    assert result.get("error") == error, (
        f"expected error={error!r} for out-of-allowlist call, got {result!r}"
    )
    return result


def assert_egress_covers_url(allowed_egress: Sequence[str], url: str) -> None:
    """Assert ``url``'s origin is covered by manifest ``allowed_egress`` entries."""
    parts = urlsplit(url)
    if not parts.scheme or not parts.hostname:
        raise AssertionError(f"contract URL must be absolute with host: {url!r}")
    origin = f"{parts.scheme}://{parts.hostname}"
    covered = any(
        entry.rstrip("/") == origin
        or url.startswith(entry)
        or origin.startswith(entry.rstrip("/"))
        for entry in allowed_egress
    )
    assert covered, (
        f"allowed_egress {list(allowed_egress)!r} does not cover contract URL {url!r} "
        f"(origin {origin!r})"
    )


def assert_manifest_publish_corpus(
    package: str, *, expected_suffix: str = ".corpus:CORPUS"
) -> str:
    """Assert the package manifest declares a ``[publish].corpus`` reference."""
    manifest = load_star_manifest(package)
    corpus = manifest["publish"]["corpus"]
    assert isinstance(corpus, str) and corpus.endswith(expected_suffix), corpus
    return corpus
