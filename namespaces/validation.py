"""Slug validation and reserved-name checks (#29 freeze)."""

from __future__ import annotations

import re

#: Lowercase DNS-label slug: letter first, then letters/digits/hyphens (2-63 chars).
SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,62}$")

#: Fail-loud reserved ids from docs/design/namespace-provisioning.md.
RESERVED_SLUGS: frozenset[str] = frozenset({
    "orrery",
    "public",
    "mcp",
    "api",
    "www",
    "gaze",
    "resolve",
    "stars",
    "constellations",
    "wallet",
    "admin",
    "system",
})


def normalize_slug(raw: str) -> str:
    """Strip and lowercase a candidate namespace id."""
    return (raw or "").strip().lower()


def is_valid_slug(slug: str) -> bool:
    return bool(SLUG_PATTERN.fullmatch(slug))


def is_reserved_slug(slug: str) -> bool:
    return slug in RESERVED_SLUGS
