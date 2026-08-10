"""Synthetic trees for docs/frontmatter-link-asset-migrate acceptance (#171)."""

from __future__ import annotations

from typing import Final

BASELINE_TREE: Final = [
    {
        "path": "index.md",
        "content": (
            "---\n"
            "summary: Welcome page\n"
            "author: orrery\n"
            "---\n\n"
            "# Welcome\n\n"
            "See the [guide](./guide.md#details) and ![logo](./assets/logo.png).\n"
        ),
    },
    {
        "path": "guide.md",
        "content": (
            "# Guide\n\n"
            "## Details\n\n"
            "Back to [home](./index.md).\n"
        ),
    },
    {
        "path": "assets/logo.png",
        "content": "PNG_PLACEHOLDER",
    },
]

REDIRECT_RULES: Final = {
    "field_renames": {"summary": "description"},
    "path_redirects": {"guide.md": "handbook.md"},
    "anchor_redirects": {"details": "overview"},
    "supported_asset_extensions": [".png", ".svg"],
    "execution_grants": [],
}

REDIRECT_TREE: Final = [
    {
        "path": "index.md",
        "content": (
            "---\n"
            "summary: Welcome page\n"
            "---\n\n"
            "# Welcome\n\n"
            "See [guide](./guide.md#details).\n"
        ),
    },
    {
        "path": "handbook.md",
        "content": (
            "# Handbook\n\n"
            "## Overview\n\n"
            "Target after redirect.\n"
        ),
    },
]

UNSAFE_TREE: Final = [
    {
        "path": "index.md",
        "content": (
            "# Escape\n\n"
            "Bad [link](../../etc/passwd) and ![bin](./assets/tool.exe).\n\n"
            "Remote [docs](https://example.com/docs) and broken [missing](./gone.md).\n"
        ),
    },
]

UNSAFE_RULES: Final = {
    "field_renames": {},
    "path_redirects": {},
    "supported_asset_extensions": [".png", ".svg"],
    "execution_grants": [],
}
